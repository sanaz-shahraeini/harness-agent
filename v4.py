import json
from pathlib import Path
import sys
from openai import OpenAI

from dotenv import load_dotenv
import os

load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

api_key = os.getenv("OPENROUTER_API_KEY", "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")

client = OpenAI(
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

# فایل متنی/مارک‌داون برای ذخیره سوابق و ترجیحات
MEMORY_FILE = Path("memory.md")


# ۱. توابع مدیریت حافظه (Memory Management)
def load_memory() -> str:
    """خواندن محتوای حافظه در صورت وجود فایل"""
    if not MEMORY_FILE.exists():
        return ""
    return MEMORY_FILE.read_text(encoding="utf-8")


def save_memory(content: str) -> str:
    """ذخیره یا بازنویسی داده‌های کلیدی در حافظه پایدار"""
    MEMORY_FILE.write_text(content, encoding="utf-8")
    return "Memory updated successfully."


# ۲. ابزارهای فایل محلی
def list_files():
    """لیست کردن فایل‌های داخل دایرکتوری workspace"""
    return [f.name for f in WORKSPACE_DIR.iterdir() if f.is_file()]


def read_file(file_name: str):
    """خواندن محتوای یک فایل مشخص از workspace"""
    file_path = WORKSPACE_DIR / file_name
    if not file_path.exists():
        return f"Error: File '{file_name}' does not exist."
    return file_path.read_text(encoding="utf-8")


# دیکشنری نگاشت ابزارها (ابزار save_memory در اختیار ایجنت قرار می‌گیرد)
tools = {
    "list_files": list_files,
    "read_file": read_file,
    "save_memory": save_memory,
}

# ۳. تعریف Tool Schemas
tool_schemas = [
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
            "name": "save_memory",
            "description": "Save important user preferences, personal facts, or context into persistent memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The complete updated memory content to persist.",
                    }
                },
                "required": ["content"],
            },
        },
    },
]


# ۴. چرخه عاملی همراه با تزریق حافظه به پرامپت سیستمی
def chat(prompt: str) -> str:
    # الف) بازیابی حافظه در آغاز اجرای دستور
    memory_content = load_memory()

    # ب) ساخت System Prompt داینامیک حاوی حافظه
    system_prompt = (
        "You are a helpful personal assistant.\n\n"
        f"Persistent Memory:\n{memory_content if memory_content else 'No memory saved yet.'}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tool_schemas,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or ""

        messages.append(message)

        for call in message.tool_calls:
            arguments = json.loads(call.function.arguments)
            tool_name = call.function.name

            print(f"[Tool Execution] Calling '{tool_name}' with args: {arguments}")

            if tool_name in tools:
                result = tools[tool_name](**arguments)
            else:
                result = f"Error: Tool '{tool_name}' not found."

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result),
                }
            )


if __name__ == "__main__":
    print("Agent with Persistent Memory ready. Type your prompt ('q' to quit):\n")
    while True:
        try:
            user_input = input("You: ")
            if user_input.strip().lower() in ("q", "quit", "exit"):
                break
            if not user_input.strip():
                continue

            response = chat(user_input)
            print(f"\nAssistant: {response}\n")

        except KeyboardInterrupt:
            print("\nExiting...")
            break