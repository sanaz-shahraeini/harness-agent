import asyncio
from contextlib import AsyncExitStack
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

from dotenv import load_dotenv
import os

load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

api_key = os.getenv("OPENROUTER_API_KEY", "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")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
    default_headers={
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Local Agent Harness",
    },
)

MODEL = "qwen/qwen3.8-27b:free"

WORKSPACE_DIR = Path("workspace")
WORKSPACE_DIR.mkdir(exist_ok=True)


# ۱. ابزارهای محلی پایتون (Local Tools)
def list_files():
    """لیست کردن فایل‌های داخل دایرکتوری workspace"""
    return [f.name for f in WORKSPACE_DIR.iterdir() if f.is_file()]


def read_file(file_name: str):
    """خواندن محتوای یک فایل مشخص از workspace"""
    file_path = WORKSPACE_DIR / file_name
    if not file_path.exists():
        return f"Error: File '{file_name}' does not exist."
    return file_path.read_text(encoding="utf-8")


def write_file(file_name: str, content: str):
    """ایجاد یا بازنویسی یک فایل جدید در workspace"""
    file_path = WORKSPACE_DIR / file_name
    file_path.write_text(content, encoding="utf-8")
    return f"File '{file_name}' written successfully."


local_tools = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
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
            "description": "Read the contents of a specific file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "The name of the file to read.",
                    }
                },
                "required": ["file_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite content to a file in the workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "The name of the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write into the file.",
                    },
                },
                "required": ["file_name", "content"],
            },
        },
    },
]

# ۲. پیکربندی سرورهای MCP (اجرا از طریق stdio و دستور uvx)
MCP_SERVERS = {
    "time": StdioServerParameters(
        command="uvx",
        args=["mcp-server-time"],
    ),
    "fetch": StdioServerParameters(
        command="uvx",
        args=["mcp-server-fetch"],
    ),
}

# نگاشت نام ابزار به سشن MCP مربوطه و لیست تجمیعی اسکیمای ابزارها
mcp_sessions: dict[str, ClientSession] = {}
all_tool_schemas = list(local_tool_schemas)
exit_stack = AsyncExitStack()


# ۳. برقراری اتصال به سرورهای MCP و کشف داینامیک ابزارها (Discovery)
async def connect_to_mcp_servers():
    for name, server_params in MCP_SERVERS.items():
        print(f"Connecting to MCP server: '{name}'...")
        # باز کردن استریم‌های ورودی/خروجی استاندارد
        read_stream, write_stream = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        session = await exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        # دریافت لیست ابزارهای رجیستر شده روی این سرور
        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            mcp_sessions[tool.name] = session

            # تبدیل خودکار input_schema سرور MCP به قالب OpenAI Function Calling
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
        print(f"MCP server '{name}' connected successfully.")


# ۴. تابع ناهمگام اجرای ابزار (تفکیک ابزار محلی و MCP)
async def call_tool(tool_name: str, arguments: dict):
    if tool_name in local_tools:
        return local_tools[tool_name](**arguments)

    if tool_name in mcp_sessions:
        session = mcp_sessions[tool_name]
        result = await session.call_tool(tool_name, arguments=arguments)

        # استخراج متن پاسخ از آبجکت محتوای MCP
        content_texts = [
            item.text for item in result.content if getattr(item, "type", "") == "text"
        ]
        return "\n".join(content_texts) if content_texts else str(result.content)

    return f"Error: Tool '{tool_name}' not found."


# ۵. چرخه عاملی ناهمگام (Async Agentic Loop)
async def run_agent(prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You are a helpful personal assistant."},
        {"role": "user", "content": prompt},
    ]

    while True:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=all_tool_schemas,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or ""

        messages.append(message)

        for call in message.tool_calls:
            arguments = json.loads(call.function.arguments)
            tool_name = call.function.name

            print(f"[Tool Execution] Calling '{tool_name}' with args: {arguments}")
            result = await call_tool(tool_name, arguments)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result),
                }
            )


# ۶. نقطه ورود اصلی و مدیریت چرخه حیات سشن‌ها
async def main():
    try:
        await connect_to_mcp_servers()
        print("\nAgent with MCP ready. Type your prompt ('q' to quit):\n")

        while True:
            # دریافت ورودی کاربر از کنسول
            user_input = await asyncio.to_thread(input, "You: ")
            if user_input.strip().lower() in ("q", "quit", "exit"):
                break
            if not user_input.strip():
                continue

            response = await run_agent(user_input)
            print(f"\nAssistant: {response}\n")

    finally:
        # بستن تمیز کانکشن‌ها و ساب‌پروسس‌های سرورهای MCP
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())