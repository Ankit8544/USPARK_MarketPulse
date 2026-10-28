from dotenv import load_dotenv
import os
import google.generativeai as genai
import requests

# Load environment variables
load_dotenv()

# Google Gemini API credentials
GEMINI_API_KEYS = [
    (os.getenv("ankitkumar875740")),
    (os.getenv("kingoflovee56")), 
    (os.getenv("bloodycrewff"))
    ]

# Get Valid Gemini API Key
def get_valid_api_key():
    for key in GEMINI_API_KEYS:
        try:
            genai.configure(api_key=key)
            genai.GenerativeModel('gemini-1.5-pro')  # Only configures the model without generating content
            return key
        except Exception as e:
            print(f"API key {key} failed: {e}")
    return None

# Get a valid Gemini API key
GEMINI_API_KEY = get_valid_api_key()

# Check if a valid API key was found
if not GEMINI_API_KEY:
    raise Exception("No valid Gemini API key found.")

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def Gemini(prompt: str) -> str:
    """Send a prompt to Gemini using REST."""
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }

    try:
        resp = requests.post(
            BASE_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=10
        )
    except Exception as e:
        print("Request Error:", e)
        return "🚫 AI is unavailable. Try again later."

    if resp.status_code != 200:
        print("API Error:", resp.status_code, resp.text[:200])
        return "🚫 AI is unavailable. Try again later."

    # Extract text safely
    try:
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        return parts[0]["text"].strip()
    except:
        return "⚠️ Unable to parse response."

def AI_Generated_Answer(prompt: str) -> str:
    """Wrapper that removes markdown symbols."""
    response = Gemini(prompt)
    return response.replace("*", "")

