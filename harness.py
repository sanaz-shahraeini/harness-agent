import asyncio
from contextlib import AsyncExitStack
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# مسیرها و دایرکتوری‌های پروژه
ROOT_DIR = Path(__file__).parent if "__file__" in locals() else Path.cwd()
WORKSPACE_DIR = ROOT_DIR / "workspace"
MEMORY_FILE = ROOT_DIR / "memory.md"
MCP_CONFIG_FILE = ROOT_DIR / "mcp_servers.json"

WORKSPACE_DIR.mkdir(exist_ok=True)

# تنظیمات مدل‌ها (امکان سوییچ بین مدل‌های محلی و ابری)
MODEL_CONFIGS = {
    "openrouter": {
        "model": "qwen/qwen3.8-27b:free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
    },
    "local": {
        "model": "qwen2.5:3b",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
    "local_small": {
        "model": "qwen2.5:1.5b",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
    "gpt": {
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
        "api_key": os.getenv("OPENAI_API_KEY", ""),
    },
}

current_model_key = "openrouter"


def get_client(model_key: str) -> tuple[AsyncOpenAI, str]:
    """تولید کلاینت متناسب با مدل انتخاب‌شده"""
    config = MODEL_CONFIGS[model_key]
    client = AsyncOpenAI(
        base_url=config.get("base_url"),
        api_key=config.get("api_key") or "dummy_key",
    )
    return client, config["model"]


# --- مدیریت حافظه پایدار ---
def load_memory() -> str:
    if not MEMORY_FILE.exists():
        return ""
    return MEMORY_FILE.read_text(encoding="utf-8")


def save_memory(content: str) -> str:
    MEMORY_FILE.write_text(content, encoding="utf-8")
    return "Memory successfully updated."


# --- ابزارهای محلی سیستم ---
def list_files():
    return [f.name for f in WORKSPACE_DIR.iterdir() if f.is_file()]


def read_file(file_name: str):
    file_path = WORKSPACE_DIR / file_name
    if not file_path.exists():
        return f"Error: File '{file_name}' does not exist."
    return file_path.read_text(encoding="utf-8")


def write_file(file_name: str, content: str):
    file_path = WORKSPACE_DIR / file_name
    file_path.write_text(content, encoding="utf-8")
    return f"File '{file_name}' written successfully."


local_tools = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "save_memory": save_memory,
}

local_tool_schemas = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the workspace directory.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "The file name"}
                },
                "required": ["file_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite content to a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "The file name"},
                    "content": {"type": "string", "description": "Text content to write"},
                },
                "required": ["file_name", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save critical user details or preferences to persistent memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Complete updated memory content"}
                },
                "required": ["content"],
            },
        },
    },
]

# متغیرهای پروتکل MCP
mcp_sessions: dict[str, ClientSession] = {}
all_tool_schemas = list(local_tool_schemas)
exit_stack = AsyncExitStack()


# --- اتصال داینامیک به سرورهای MCP از روی کانفیگ JSON ---
async def connect_mcp_servers():
    if not MCP_CONFIG_FILE.exists():
        print("Warning: mcp_servers.json not found. Proceeding with local tools only.")
        return

    with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    servers = config.get("mcpServers", {})
    for name, server_info in servers.items():
        try:
            print(f"Connecting to MCP Server '{name}'...")
            params = StdioServerParameters(
                command=server_info["command"],
                args=server_info.get("args", []),
                env=server_info.get("env"),
            )
            read_stream, write_stream = await exit_stack.enter_async_context(
                stdio_client(params)
            )
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()

            tools_res = await session.list_tools()
            for tool in tools_res.tools:
                mcp_sessions[tool.name] = session
                schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", {})
                all_tool_schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": schema,
                        },
                    }
                )
            print(f"Server '{name}' connected successfully.")
        except Exception as e:
            print(f"Failed to connect to MCP server '{name}': {e}")


# --- تابع توزیع و اجرای ابزار ---
async def call_tool(tool_name: str, arguments: dict):
    if tool_name in local_tools:
        return local_tools[tool_name](**arguments)

    if tool_name in mcp_sessions:
        session = mcp_sessions[tool_name]
        res = await session.call_tool(tool_name, arguments=arguments)
        text_outputs = [
            item.text for item in res.content if getattr(item, "type", "") == "text"
        ]
        return "\n".join(text_outputs) if text_outputs else str(res.content)

    return f"Error: Tool '{tool_name}' not found."


# --- اجرای حلقه عاملی (Agentic Loop) ---
async def run_agent(prompt: str) -> str:
    client, model_name = get_client(current_model_key)
    memory_content = load_memory()

    system_prompt = (
        "You are a helpful personal assistant equipped with execution tools.\n\n"
        f"Memory Context:\n{memory_content if memory_content else 'No memory saved yet.'}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    while True:
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=all_tool_schemas,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or ""

        messages.append(message)

        for call in message.tool_calls:
            args = json.loads(call.function.arguments)
            tool_name = call.function.name

            print(f"[Tool Execution] Calling '{tool_name}' with args: {args}")
            tool_result = await call_tool(tool_name, args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(tool_result),
                }
            )


# --- پردازش دستورات کنترلی خط فرمان (Slash Commands) ---
def handle_slash_command(cmd: str) -> bool:
    global current_model_key
    parts = cmd.strip().split()
    base_cmd = parts[0].lower()

    if base_cmd in ("/quit", "/exit"):
        return False

    if base_cmd == "/models":
        print("\nAvailable Models:")
        for key, conf in MODEL_CONFIGS.items():
            active = " (Active)" if key == current_model_key else ""
            print(f"  - {key}: {conf['model']}{active}")
        print()

    elif base_cmd == "/model":
        if len(parts) > 1 and parts[1] in MODEL_CONFIGS:
            current_model_key = parts[1]
            print(f"Switched model to '{current_model_key}' ({MODEL_CONFIGS[current_model_key]['model']})\n")
        else:
            print(f"Usage: /model <name>. Available: {list(MODEL_CONFIGS.keys())}\n")

    elif base_cmd == "/tools":
        print("\nLoaded Tools:")
        for s in all_tool_schemas:
            name = s["function"]["name"]
            is_mcp = "MCP" if name in mcp_sessions else "Local"
            print(f"  - {name} [{is_mcp}]: {s['function'].get('description', '')}")
        print()

    elif base_cmd == "/memory":
        print("\nCurrent Memory Content:")
        mem = load_memory()
        print(mem if mem else "(Memory is empty)")
        print()

    else:
        print(f"Unknown command: {base_cmd}\n")

    return True


# --- چرخه اصلی برنامه ---
async def main():
    try:
        print("Starting Agentic Harness...")
        await connect_mcp_servers()
        print(f"\nHarness Ready. Active Model: '{current_model_key}'")
        print("Commands: /models, /model <name>, /tools, /memory, /quit\n")

        while True:
            user_input = await asyncio.to_thread(input, f"[{current_model_key}] You: ")
            trimmed = user_input.strip()

            if not trimmed:
                continue

            if trimmed.startswith("/"):
                keep_running = handle_slash_command(trimmed)
                if not keep_running:
                    break
                continue

            response = await run_agent(trimmed)
            print(f"\nAssistant:\n{response}\n")

    finally:
        print("\nShutting down MCP servers and cleaning up...")
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())