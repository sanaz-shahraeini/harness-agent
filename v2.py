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


# ۱. تعریف ابزارهای محلی
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


tools = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
}

# ۲. تعریف Tool Schemas (اضافه شدن schema برای write_file)
tool_schemas = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
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
            "description": "Write or overwrite content to a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "The name of the file to write to.",
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


# ۳. پیاده‌سازی حلقه عاملی (The Agentic Loop)
def chat(prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You are a helpful personal assistant."},
        {"role": "user", "content": prompt},
    ]

    while True:
        # فراخوانی مدل با تاریخچه فعلی و لیست ابزارها
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tool_schemas,
        )

        message = response.choices[0].message

        # شرط خروج از حلقه: مدل تصمیم گرفته پاسخی متنی بدهد و نیازی به ابزار ندارد
        if not message.tool_calls:
            return message.content or ""

        # ثبت پیام ایجنت در تاریخچه
        messages.append(message)

        # اجرای ابزارهایی که مدل در این مرحله درخواست کرده است
        for call in message.tool_calls:
            arguments = json.loads(call.function.arguments)
            tool_name = call.function.name

            print(f"[Tool Execution] Calling '{tool_name}' with args: {arguments}")

            if tool_name in tools:
                result = tools[tool_name](**arguments)
            else:
                result = f"Error: Tool '{tool_name}' not found."

            # افزودن نتیجه اجرای ابزار به پیام‌ها برای گام بعدی مدل
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result),
                }
            )


if __name__ == "__main__":
    print("Agentic Loop Harness ready. Type your prompt ('q' to quit):\n")
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