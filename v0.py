# import os
# import sys
# from openai import OpenAI

# if sys.platform == "win32":
#     sys.stdout.reconfigure(encoding="utf-8")

# # تنظیم کلاینت برای OpenRouter
# client = OpenAI(
#     base_url="https://openrouter.ai/api/v1",
#     api_key=os.getenv("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"),  # کلید دریافتی از پنل OpenRouter
#     default_headers={
#         "HTTP-Referer": "http://localhost:3000",  # اختیاری: آدرس پروژه برای رتبه‌بندی در پنل
#         "X-Title": "Local Agent Harness",        # اختیاری: نام اپلیکیشن
#     },
# )

# # فرمت نام مدل در OpenRouter به صورت provider/model-name است
# MODEL = "qwen/qwen3.8-27b:free" 
# # یا مثلاً: "meta-llama/llama-3.3-70b-instruct" یا "openai/gpt-4o-mini"


# def chat(prompt: str) -> str:
#     response = client.chat.completions.create(
#         model=MODEL,
#         messages=[
#             {"role": "system", "content": "You are a helpful personal assistant."},
#             {"role": "user", "content": prompt},
#         ],
#     )
#     return response.choices[0].message.content or ""


# if __name__ == "__main__":
#     print("Agent connected to OpenRouter. Type your message:\n")
#     while True:
#         try:
#             user_input = input("You: ")
#             if user_input.strip().lower() in ("q", "quit", "exit"):
#                 break
#             if not user_input.strip():
#                 continue

#             response = chat(user_input)
#             print(f"\nAssistant: {response}\n")
#         except KeyboardInterrupt:
#             print("\nExiting...")
#             break

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# بارگذاری متغیرهای محیطی از .env
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# خواندن کلید از محیط یا مقدار پیش‌فرض
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


def chat(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful personal assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    print("Agent connected to OpenRouter. Type your message:\n")
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
