"""Manual smoke check: send a sample message through the AI agent.

Usage (from backend/):  python -m scripts.smoke.check_ai_agent
"""

import asyncio

from app.core.config import settings
from app.services.ai_agent import QTrackAIAgent


async def check_ai_agent():
    print(f"GROQ_API_KEY configured: {'Yes' if settings.groq_api_key else 'No'}")
    print(f"MEDICAL_SERVICES: {settings.medical_services}")

    agent = QTrackAIAgent()

    message = "Details: Name is Jathin Branch: ent Phone number: 12312312353 add me in the queue"
    print(f"Testing message: {message}")

    try:
        response, context = await agent.process_message(message, "test_session")
        print(f"Response: {response}")
        print(f"Context: {context}")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_ai_agent())
