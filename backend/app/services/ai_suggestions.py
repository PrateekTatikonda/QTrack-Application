"""Keyword-based follow-up suggestions shown under AI replies."""


def generate_suggestions(user_message: str, ai_response: str) -> list:
    user_lower = user_message.lower()

    if any(word in user_lower for word in ['join', 'book', 'appointment', 'queue']):
        suggestions = [
            "Check my queue position",
            "What services are available?",
            "How long is the wait?",
            "Can I reschedule?"
        ]
    elif any(word in user_lower for word in ['status', 'position', 'wait']):
        suggestions = [
            "Reschedule my appointment",
            "Cancel my appointment",
            "Get directions to hospital",
            "What documents do I need?"
        ]
    elif any(word in user_lower for word in ['reschedule', 'change']):
        suggestions = [
            "Check available time slots",
            "Change to different department",
            "Get confirmation details",
            "Contact support"
        ]
    elif any(word in user_lower for word in ['emergency', 'urgent', 'pain']):
        suggestions = [
            "Call emergency services: 911",
            "Find nearest emergency room",
            "Urgent care options",
            "Ambulance service"
        ]
    else:
        suggestions = [
            "Join queue",
            "Check queue status",
            "Hospital information",
            "Emergency services"
        ]

    return suggestions[:4]
