from dotenv import load_dotenv
import os
import requests

# Load environment variables
load_dotenv()

# OpenRouter API credentials
OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3")
]

OPENROUTER_API_KEYS = [
    key.strip() for key in OPENROUTER_API_KEYS
    if key and key.strip()
]

# OpenRouter model
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/free"
)

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def Gemini(prompt: str) -> str:
    """Send a prompt to OpenRouter using REST."""

    if not OPENROUTER_API_KEYS:
        print("API Error: No OpenRouter API key found.")
        return "🚫 AI is unavailable. Try again later."

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    for api_key in OPENROUTER_API_KEYS:

        try:
            resp = requests.post(
                BASE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )

        except Exception as e:
            print("Request Error:", e)
            return "🚫 AI is unavailable. Try again later."

        if resp.status_code == 200:

            try:
                data = resp.json()

                return data["choices"][0]["message"]["content"].strip()

            except Exception as e:
                print("Response Parse Error:", e)
                return "⚠️ Unable to parse response."

        print(
            "API Error:",
            resp.status_code,
            resp.text[:200]
        )

        if resp.status_code not in (401, 402, 403, 429):
            break

    return "🚫 AI is unavailable. Try again later."


def AI_Generated_Answer(prompt: str) -> str:
    """Wrapper that removes markdown symbols."""

    response = Gemini(prompt)

    return response.replace("*", "")