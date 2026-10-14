"""Pydantic models for the AI agent API and conversation state."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ConversationMessage(BaseModel):
    role: str  # "system", "user", "assistant", "tool"
    content: str
    timestamp: Optional[datetime] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class PatientContext(BaseModel):
    patient_id: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    branch_id: Optional[str] = None
    last_visit: Optional[datetime] = None
    medical_conditions: List[str] = []
    preferred_language: str = "en"
    queue_position: Optional[int] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    language: Optional[str] = "en"
    patient_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    patient_context: Optional[Dict[str, Any]] = None
    suggestions: Optional[list] = None
    detected_language: Optional[str] = None


class WhatsAppWebhook(BaseModel):
    """WhatsApp Business API webhook structure"""
    object: str
    entry: list
