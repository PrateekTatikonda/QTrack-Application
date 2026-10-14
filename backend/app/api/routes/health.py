from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health-check")
def health_check():
    return {"message": "QTrack backend is working!"}


@router.get("/")
async def root():
    return {
        "message": "QTrack API v2.0 - AI-Powered Hospital Queue Management",
        "features": [
            "Queue Management",
            "Real-time Updates",
            "AI Conversational Agent",
            "WhatsApp Integration"
        ],
        "endpoints": {
            "queue": "/join-queue, /live-queue/{branch_id}",
            "ai_agent": "/ai/chat, /ai/whatsapp/webhook",
            "health": "/health-check, /ai/health"
        }
    }
