"""Manual smoke check: verify the Groq API key and model respond.

Usage (from backend/):  python -m scripts.smoke.check_groq
"""

from app.core.config import settings


def check_groq():
    api_key = settings.groq_api_key
    print("API key loaded" if api_key else "No API key found")
    if not api_key:
        return

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": "Say hello in one word"}],
            model=settings.ai_model,
            max_tokens=10,
        )
        print(f"API response: {chat_completion.choices[0].message.content}")
        print("Groq API key is working.")
    except ImportError as e:
        print(f"Import error: {e} (pip install groq)")
    except Exception as e:
        print(f"API error: {e}")


if __name__ == "__main__":
    check_groq()
