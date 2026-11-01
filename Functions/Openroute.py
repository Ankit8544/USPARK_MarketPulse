from dotenv import load_dotenv
import os
from datetime import datetime
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


def web_search(query):
    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": os.getenv("TAVILY_API_KEY"),
            "query": query,
            "topic": "general",
            "search_depth": "advanced",
            "max_results": 7,
            "include_answer": True
        },
        timeout=30
    )

    response.raise_for_status()
    return response.json()


def Gemini(prompt: str) -> str:

    if not OPENROUTER_API_KEYS:
        return "AI unavailable."

    current_date = datetime.now().strftime("%d %B %Y")

    search_data = web_search(prompt)

    system_prompt = f"""
You are a real-time research AI.

Current date: {current_date}

RULES:
1. Always prioritize latest available information.
2. Never present old information as current.
3. Verify facts using search results.
4. For stock questions, distinguish live price,
   historical price and market news.
5. If information is unavailable, say so.
6. Include source URLs.
7. Mention the date of information.
8. Never invent facts.
"""

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""
Question: {prompt}

Latest web search results:
{search_data}
"""
            }
        ],
        "temperature": 0.2
    }

    # Keep your existing API request and response code here.


def AI_Generated_Answer(prompt: str) -> str:
    """Wrapper that removes markdown symbols."""

    response = Gemini(prompt)

    return response.replace("*", "")