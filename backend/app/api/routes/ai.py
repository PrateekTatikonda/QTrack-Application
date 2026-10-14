"""
AI Agent endpoints for QTrack conversational interface
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.config import settings
from app.schemas.ai import ChatRequest, ChatResponse, PatientContext, WhatsAppWebhook
from app.services.ai_agent import QTrackAIAgent
from app.services.ai_suggestions import generate_suggestions
from app.services.whatsapp import send_whatsapp_response

logger = logging.getLogger(__name__)

ai_agent = QTrackAIAgent()

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Main chat endpoint for conversational AI agent
    
    This endpoint processes natural language queries and executes
    queue management actions through function calling.
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Detect language if not specified
        detected_language = request.language or ai_agent.detect_language(request.message)
        
        # Convert patient context if provided
        patient_context = None
        if request.patient_context:
            patient_context = PatientContext(**request.patient_context)
        
        # Process the message through AI agent
        response_text, updated_context = await ai_agent.process_message(
            user_message=request.message,
            session_id=session_id,
            patient_context=patient_context,
            language=detected_language
        )
        
        # Generate contextual suggestions based on conversation
        suggestions = generate_suggestions(request.message, response_text)
        
        # Schedule cleanup in background
        background_tasks.add_task(ai_agent.cleanup_old_conversations)
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            patient_context=updated_context.dict() if updated_context else None,
            suggestions=suggestions,
            detected_language=detected_language
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/whatsapp/webhook")
async def whatsapp_webhook(webhook_data: WhatsAppWebhook, background_tasks: BackgroundTasks):
    """
    WhatsApp Business API webhook endpoint
    
    Receives messages from WhatsApp and processes them through the AI agent
    """
    try:
        for entry in webhook_data.entry:
            if 'changes' in entry:
                for change in entry['changes']:
                    if change.get('field') == 'messages':
                        value = change.get('value', {})
                        messages = value.get('messages', [])
                        
                        for message in messages:
                            if message.get('type') == 'text':
                                # Extract message details
                                from_number = message.get('from')
                                message_text = message.get('text', {}).get('body', '')
                                message_id = message.get('id')
                                
                                # Process message through AI agent
                                session_id = f"whatsapp_{from_number}"
                                
                                # Detect language
                                detected_language = ai_agent.detect_language(message_text)
                                
                                response_text, updated_context = await ai_agent.process_message(
                                    user_message=message_text,
                                    session_id=session_id,
                                    language=detected_language
                                )
                                
                                # Send response back via WhatsApp
                                background_tasks.add_task(
                                    send_whatsapp_response,
                                    from_number,
                                    response_text
                                )
                                
                                logger.info(f"Processed WhatsApp message from {from_number}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing error")

@router.get("/whatsapp/webhook")
async def verify_whatsapp_webhook(
    hub_mode: str = None,
    hub_verify_token: str = None, 
    hub_challenge: str = None
):
    """
    WhatsApp webhook verification endpoint
    """
    verify_token = settings.whatsapp_verify_token
    
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return int(hub_challenge)
    else:
        raise HTTPException(status_code=403, detail="Verification failed")

@router.get("/conversation/{session_id}")
async def get_conversation_history(session_id: str):
    """
    Get conversation history for a session
    """
    try:
        if session_id not in ai_agent.conversations:
            raise HTTPException(status_code=404, detail="Session not found")
        
        messages = ai_agent.conversations[session_id]
        
        # Convert to response format (exclude system messages)
        history = []
        for msg in messages:
            if msg.role != "system":
                history.append({
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
                })
        
        return {"session_id": session_id, "messages": history}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/conversation/{session_id}")
async def clear_conversation(session_id: str):
    """
    Clear conversation history for a session
    """
    try:
        if session_id in ai_agent.conversations:
            del ai_agent.conversations[session_id]
        
        if session_id in ai_agent.patient_contexts:
            del ai_agent.patient_contexts[session_id]
        
        return {"message": "Conversation cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Add health check for AI agent
@router.get("/health")
async def ai_agent_health():
    """
    Health check endpoint for AI agent
    """
    try:
        # Test Groq API connectivity
        test_response = await ai_agent.client.chat.completions.create(
            model=ai_agent.model,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10
        )
        
        return {
            "status": "healthy",
            "groq_api": "connected",
            "active_sessions": len(ai_agent.conversations),
            "model": ai_agent.model,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI Agent health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
