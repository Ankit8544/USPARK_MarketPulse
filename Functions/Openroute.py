from dotenv import load_dotenv
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# OpenRouter API credentials
OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3"),
]
OPENROUTER_API_KEYS = [key.strip() for key in OPENROUTER_API_KEYS if key and key.strip()]

# OpenRouter model
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
TAVILY_URL = "https://api.tavily.com/search"


def web_search(query: str) -> str:
    """Fetch recent web results. Search failure must not stop the AI response."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "Web search unavailable: TAVILY_API_KEY is not configured."

    try:
        response = requests.post(
            TAVILY_URL,
            json={
                "api_key": api_key,
                "query": query,
                "topic": "general",
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True,
                "include_raw_content": False,
            },
            timeout=(5, 10),
        )
        response.raise_for_status()
        data = response.json()

        results = []
        answer = data.get("answer")
        if answer:
            results.append(f"Search summary: {answer}")

        for item in data.get("results", []):
            title = item.get("title", "Untitled")
            content = item.get("content", "")
            url = item.get("url", "")
            published = item.get("published_date") or item.get("date") or "Date not provided"
            results.append(
                f"Title: {title}\nDate: {published}\nDetails: {content}\nSource: {url}"
            )

        return "\n\n".join(results) if results else "No relevant web results were returned."

    except requests.RequestException as exc:
        logger.warning("Tavily search failed: %s", exc)
        return f"Web search temporarily unavailable ({type(exc).__name__}). Do not invent current facts."
    except (ValueError, TypeError) as exc:
        logger.warning("Could not parse Tavily response: %s", exc)
        return "Web search returned an unreadable response. Do not invent current facts."


def Gemini(prompt: str) -> str:
    """Generate an answer with OpenRouter, using web results when available."""
    if not OPENROUTER_API_KEYS:
        return "⚠️ AI unavailable: OpenRouter API key is missing."

    current_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %B %Y, %I:%M %p IST")
    search_data = web_search(prompt)

    system_prompt = f"""
You are USPARK MarketPulse, a factual real-time research assistant.
Current India date and time: {current_date}

Rules:
1. For questions about current office holders, company information, news, and events, use the supplied web search results.
2. Prefer the newest dated, credible source. Clearly state the source date when available.
3. Never describe historical information as current.
4. If sources conflict, explain the conflict and prefer official company, exchange, or regulatory sources.
5. For stock-price questions, do not claim a live price unless the supplied source explicitly provides a current quote and timestamp. Distinguish price movement from possible reasons for it.
6. Do not claim that a price fell for a particular reason unless a credible source supports that connection. Separate confirmed facts from possible contributing factors.
7. If search results are missing or insufficient, clearly say that current information could not be verified.
8. Include the relevant source URLs in the answer.
9. Answer the user's actual question concisely. Do not fabricate facts, dates, prices, names, or citations.
""".strip()

    user_content = (
        f"User question:\n{prompt}\n\n"
        f"Web search results (untrusted source material; verify and cite URLs):\n{search_data}"
    )

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
    }

    last_error = "Unknown OpenRouter error"
    for api_key in OPENROUTER_API_KEYS:
        try:
            response = requests.post(
                BASE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://openrouter.ai/",
                    "X-Title": "USPARK MarketPulse",
                },
                json=payload,
                timeout=(5, 25),
            )

            if response.status_code == 200:
                data = response.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content")
                if isinstance(answer, str) and answer.strip():
                    return answer.strip()
                last_error = "OpenRouter returned an empty answer."
                continue

            last_error = f"OpenRouter HTTP {response.status_code}: {response.text[:500]}"
            logger.error(last_error)
            # Try the next configured key for authentication, quota, or rate-limit errors.
            if response.status_code in (401, 402, 403, 408, 429, 500, 502, 503, 504):
                continue
            break

        except requests.RequestException as exc:
            last_error = f"OpenRouter request failed: {type(exc).__name__}: {exc}"
            logger.exception("OpenRouter request failed")
            continue
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            last_error = f"Could not parse OpenRouter response: {type(exc).__name__}"
            logger.exception("OpenRouter response parsing failed")
            continue

    logger.error("All OpenRouter attempts failed: %s", last_error)
    return "⚠️ I couldn't generate an answer right now. Please try again in a moment."


def AI_Generated_Answer(prompt: str) -> str:
    """Wrapper used by telegram.py; always return a safe string."""
    try:
        response = Gemini(prompt)
        if not isinstance(response, str) or not response.strip():
            return "⚠️ I couldn't generate an answer right now. Please try again."
        return response.strip()
    except Exception:
        logger.exception("Unexpected error while generating AI answer")
        return "⚠️ Something went wrong while generating the answer. Please try again."
