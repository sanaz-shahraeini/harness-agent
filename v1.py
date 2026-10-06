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


# دایرکتوری کاری برای اجرای عملیات خواندن/نوشتن ابزارها
WORKSPACE_DIR = Path("workspace")
WORKSPACE_DIR.mkdir(exist_ok=True)


# ۱. توابع محلی پایتون (ابزارها)
def list_files():
    """لیست کردن فایل‌های داخل دایرکتوری workspace"""
    return [f.name for f in WORKSPACE_DIR.iterdir() if f.is_file()]


def read_file(file_name: str):
    """خواندن محتوای یک فایل مشخص از workspace"""
    file_path = WORKSPACE_DIR / file_name
    if not file_path.exists():
        return f"Error: File '{file_name}' does not exist."
    return file_path.read_text(encoding="utf-8")


# دیکشنری نگاشت نام ابزار به تابع پایتونی
tools = {
    "list_files": list_files,
    "read_file": read_file,
}

# ۲. تعریف Tool Schema بر اساس استاندارد OpenAI Function Calling
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
]


# ۳. تابع ارتباط و هندل کردن فراخوانی ابزار
def chat(prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You are a helpful personal assistant."},
        {"role": "user", "content": prompt},
    ]

    # ارسال پیام‌ها به همراه ساختار ابزارها
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tool_schemas,
    )

    message = response.choices[0].message

    # اگر مدل ابزاری صدا نزد، همان متن خروجی بازگردانده می‌شود
    if not message.tool_calls:
        return message.content or ""

    # برای حفظ کانتکست مکالمه، پیام خود مدل را ابتدا به تاریخچه اضافه می‌کنیم
    messages.append(message)

    # پیمایش ابزارهایی که مدل درخواست اجرای آن‌ها را داده است
    for call in message.tool_calls:
        arguments = json.loads(call.function.arguments)
        tool_name = call.function.name

        print(f"[Tool Execution] Calling '{tool_name}' with arguments: {arguments}")

        # اجرای تابع محلی
        if tool_name in tools:
            result = tools[tool_name](**arguments)
        else:
            result = f"Error: Tool '{tool_name}' not found."

        # تزریق خروجی ابزار با نقش 'tool' و شناسه فراخوانی
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(result),
            }
        )

    # ارسال مجدد تاریخچه حاوی نتایج ابزار به مدل جهت دریافت پاسخ تحلیلی نهایی
    final_response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    return final_response.choices[0].message.content or ""


if __name__ == "__main__":
    print("Agent with Tool Calling ready. Type your prompt ('q' to quit):\n")
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