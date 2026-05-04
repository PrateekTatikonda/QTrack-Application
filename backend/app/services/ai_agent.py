"""
QTrack AI Conversational Agent
Integrates with Groq API for natural language processing and function calling
"""

import json
import os
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import re
import aiohttp

from groq import AsyncGroq
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

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

class QTrackAIAgent:
    def __init__(self):
        # Load medical services from environment
        self.medical_services = self._load_medical_services()
        print(f"AI Agent Init - Medical services loaded: {self.medical_services}")
        
        # Check if Groq API key is available
        groq_api_key = os.getenv("GROQ_API_KEY")
        
        # Debug logging
        print(f"AI Agent Init - GROQ_API_KEY found: {bool(groq_api_key)}")
        if groq_api_key:
            print(f"AI Agent Init - Key starts with: {groq_api_key[:10]}...")
        else:
            print("AI Agent Init - No GROQ_API_KEY environment variable found")
            print(f"AI Agent Init - Available env vars: {[k for k in os.environ.keys() if 'GROQ' in k.upper()]}")
        
        if not groq_api_key:
            logger.warning("GROQ_API_KEY not found. AI agent will operate in mock mode.")
            self.client = None
        else:
            try:
                self.client = AsyncGroq(api_key=groq_api_key)
                logger.info("Groq client initialized successfully")
                print("✅ Groq client created successfully!")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
                self.client = None
        
        self.model = "llama-3.1-8b-instant"  # Fast and efficient for queue management
        self.conversations: Dict[str, List[ConversationMessage]] = {}
        self.patient_contexts: Dict[str, PatientContext] = {}
        
        # Available function tools for the AI agent - dynamically load services
        self.tools = self._create_function_tools()
    
    def _load_medical_services(self) -> List[str]:
        """Load medical services from environment configuration"""
        services_str = os.getenv("MEDICAL_SERVICES", "general,emergency")
        print(f"DEBUG - Raw MEDICAL_SERVICES: {services_str}")
        services = [service.strip().lower() for service in services_str.split(",")]
        print(f"DEBUG - Processed services: {services}")
        return services
    
    def _create_function_tools(self) -> List[Dict]:
        """Create function tools with dynamic medical services"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "join_queue",
                    "description": "Add a patient to the hospital queue for a specific branch and service",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Full name of the patient"
                            },
                            "phone": {
                                "type": "string", 
                                "description": "Patient's phone number with country code"
                            },
                            "branch_id": {
                                "type": "string",
                                "description": "Hospital branch/location identifier. Must be one of: 'main', 'north', 'south', 'east'. DO NOT use medical service names here.",
                                "enum": ["main", "north", "south", "east"]
                            },
                            "service_type": {
                                "type": "string",
                                "description": "Medical department/service type (lowercase). This is the medical specialty, NOT the hospital location.",
                                "enum": self.medical_services
                            }
                        },
                        "required": ["name", "phone", "branch_id", "service_type"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "get_queue_status",
                    "description": "Get current queue position and waiting time for a patient",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {
                                "type": "string",
                                "description": "Patient's phone number to lookup queue position"
                            },
                            "branch_id": {
                                "type": "string", 
                                "description": "Hospital branch identifier"
                            }
                        },
                        "required": ["phone", "branch_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "reschedule_appointment",
                    "description": "Reschedule or modify an existing appointment/queue position",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {
                                "type": "string",
                                "description": "Patient's phone number"
                            },
                            "branch_id": {
                                "type": "string",
                                "description": "Current branch identifier"
                            },
                            "new_branch_id": {
                                "type": "string", 
                                "description": "New branch identifier if changing location"
                            },
                            "new_service_type": {
                                "type": "string",
                                "description": "New service type if changing",
                                "enum": self.medical_services
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for rescheduling"
                            }
                        },
                        "required": ["phone", "branch_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_branch_info",
                    "description": "Get information about hospital branches, services, and wait times",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "branch_id": {
                                "type": "string",
                                "description": "Branch identifier, or 'all' for all branches"
                            },
                            "service_type": {
                                "type": "string", 
                                "description": "Specific service to check availability"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "cancel_appointment",
                    "description": "Cancel a patient's appointment or remove from queue",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {
                                "type": "string",
                                "description": "Patient's phone number"
                            },
                            "branch_id": {
                                "type": "string",
                                "description": "Branch identifier"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for cancellation"
                            }
                        },
                        "required": ["phone", "branch_id"]
                    }
                }
            }
        ]

    def get_system_prompt(self, language: str = "en") -> str:
        """Get system prompt based on user's preferred language"""
        # Format available services for display
        services_display = ", ".join([service.title() for service in self.medical_services])
        
        prompts = {
            "en": f"""You are QTrack Assistant, an AI-powered hospital queue management agent. You help patients with:

🏥 **Core Services:**
- Join hospital queues for different departments
- Check current queue position and estimated wait time  
- Reschedule appointments and change departments
- Get information about hospital branches and services
- Handle appointment cancellations

🏨 **Available Medical Services:**
{services_display}

🎯 **Your Personality:**
- Professional yet warm and empathetic
- Clear and concise communication
- Multilingual support when needed
- Patient-focused and understanding
- Always prioritize urgent medical needs

📋 **Important Guidelines:**
- ALWAYS ask for phone number and branch preference for queue operations
- For symptoms, be supportive but remind that you're not providing medical advice
- If patient mentions emergency symptoms (chest pain, difficulty breathing, severe bleeding), immediately direct them to emergency services
- Collect patient name, phone, branch, and service type before joining queue
- Use function calls to interact with the queue system
- Be conversational and natural - patients are often stressed or worried
- **CRITICAL**: When calling functions, use lowercase service names (e.g., 'ent', 'cardiology', 'general') exactly as they appear in the available services list
- **IMPORTANT DISTINCTION**: 
  * BRANCHES are hospital locations: main, north, south, east
  * SERVICES are medical departments: ent, cardiology, general, etc.
  * When users say "Branch: ENT" they likely mean "Service: ENT" at the main branch
  * Always clarify if unclear and default to main branch for services
  * **NEVER USE ENT/CARDIOLOGY/etc AS BRANCH_ID - THESE ARE SERVICES!**
  * **ALWAYS USE 'main', 'north', 'south', 'east' AS BRANCH_ID VALUES**

🚨 **Emergency Protocol:**
If patient mentions: chest pain, difficulty breathing, severe bleeding, loss of consciousness, severe allergic reactions, or says "emergency" - immediately recommend they call emergency services or go to the ER.

Remember: You're not a doctor - you're a helpful queue management assistant.""",

            "es": """Eres QTrack Assistant, un agente de IA para la gestión de colas hospitalarias. Ayudas a los pacientes con:

🏥 **Servicios Principales:**
- Unirse a colas hospitalarias para diferentes departamentos
- Verificar posición actual en cola y tiempo estimado de espera
- Reprogramar citas y cambiar departamentos  
- Obtener información sobre sucursales y servicios del hospital
- Manejar cancelaciones de citas

🎯 **Tu Personalidad:**
- Profesional pero cálido y empático
- Comunicación clara y concisa
- Soporte multilingüe cuando sea necesario
- Enfocado en el paciente y comprensivo
- Siempre priorizar necesidades médicas urgentes

En caso de emergencia, dirige inmediatamente a servicios de emergencia.""",

            "hi": """आप QTrack Assistant हैं, एक AI-संचालित अस्पताल क्यू प्रबंधन एजेंट। आप मरीजों की मदद करते हैं:

🏥 **मुख्य सेवाएं:**
- विभिन्न विभागों के लिए अस्पताल की कतारों में शामिल होना
- वर्तमान कतार स्थिति और अनुमानित प्रतीक्षा समय देखना
- अपॉइंटमेंट रीशेड्यूल करना और विभाग बदलना

आपात स्थिति में, तुरंत आपातकालीन सेवाओं का निर्देश दें।"""
        }
        return prompts.get(language, prompts["en"])

    async def process_message(
        self, 
        user_message: str, 
        session_id: str, 
        patient_context: Optional[PatientContext] = None,
        language: str = "en"
    ) -> Tuple[str, Optional[PatientContext]]:
        """Process a user message and return AI response with updated context"""
        try:
            # Initialize conversation if new session
            if session_id not in self.conversations:
                self.conversations[session_id] = [
                    ConversationMessage(
                        role="system",
                        content=self.get_system_prompt(language),
                        timestamp=datetime.now()
                    )
                ]
            
            # Store patient context
            if patient_context:
                self.patient_contexts[session_id] = patient_context

            # Add user message to conversation
            self.conversations[session_id].append(
                ConversationMessage(
                    role="user",
                    content=user_message,
                    timestamp=datetime.now()
                )
            )

            # Convert conversation to Groq format
            messages = []
            for msg in self.conversations[session_id]:
                message_dict = {"role": msg.role, "content": msg.content}
                if msg.tool_calls:
                    message_dict["tool_calls"] = msg.tool_calls
                if msg.tool_call_id:
                    message_dict["tool_call_id"] = msg.tool_call_id
                if msg.name:
                    message_dict["name"] = msg.name
                messages.append(message_dict)

            # Check if Groq client is available
            if not self.client:
                # Fallback response when Groq is not available
                return self.get_fallback_response(user_message, session_id), patient_context

            # Make request to Groq with function calling
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=1024
            )

            assistant_message = response.choices[0].message

            # Handle tool calls if present
            if assistant_message.tool_calls:
                # Add assistant's tool call message
                self.conversations[session_id].append(
                    ConversationMessage(
                        role="assistant",
                        content=assistant_message.content or "",
                        tool_calls=[
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in assistant_message.tool_calls
                        ],
                        timestamp=datetime.now()
                    )
                )

                # Execute tool calls
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Execute the function and get result
                    tool_result = await self.execute_function(
                        function_name, 
                        function_args, 
                        session_id
                    )

                    # Add tool result to conversation
                    self.conversations[session_id].append(
                        ConversationMessage(
                            role="tool",
                            content=json.dumps(tool_result),
                            tool_call_id=tool_call.id,
                            name=function_name,
                            timestamp=datetime.now()
                        )
                    )

                # Get final response after tool execution
                messages = []
                for msg in self.conversations[session_id]:
                    message_dict = {"role": msg.role, "content": msg.content}
                    if msg.tool_calls:
                        message_dict["tool_calls"] = msg.tool_calls
                    if msg.tool_call_id:
                        message_dict["tool_call_id"] = msg.tool_call_id
                    if msg.name:
                        message_dict["name"] = msg.name
                    messages.append(message_dict)

                final_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1024
                )

                final_content = final_response.choices[0].message.content
            else:
                final_content = assistant_message.content

            # Add final assistant message
            self.conversations[session_id].append(
                ConversationMessage(
                    role="assistant",
                    content=final_content,
                    timestamp=datetime.now()
                )
            )

            # Update patient context if needed
            updated_context = self.patient_contexts.get(session_id)

            return final_content, updated_context

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            print(f"DEBUG - Error processing message: {str(e)}")
            import traceback
            print(f"DEBUG - Full traceback: {traceback.format_exc()}")
            error_msg = "I'm sorry, I'm experiencing technical difficulties. Please try again or contact hospital staff for immediate assistance."
            return error_msg, patient_context

    async def execute_function(self, function_name: str, args: Dict, session_id: str) -> Dict:
        """Execute function calls - integrates with the actual queue system"""
        print(f"DEBUG - execute_function called: {function_name}")
        print(f"DEBUG - args: {args}")
        try:
            # Base URL for API calls
            base_url = "http://localhost:8000"
            
            if function_name == "join_queue":
                # Make actual API call to join queue
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "name": args["name"],
                        "phone": args["phone"], 
                        "branch_id": args["branch_id"],
                        "service_type": args["service_type"]
                    }
                    
                    async with session.post(f"{base_url}/join-queue", json=payload) as response:
                        print(f"DEBUG - API Response status: {response.status}")
                        if response.status == 200:
                            result = await response.json()
                            print(f"DEBUG - API Response: {result}")
                            return {
                                "success": True,
                                "queue_position": result.get("position", "Unknown"),
                                "estimated_wait_minutes": result.get("estimated_wait_minutes", 25),
                                "message": f"Successfully added {args['name']} to {args['service_type']} queue at {args['branch_id']} branch.",
                                "queue_id": result.get("queue_id", result.get("user_id"))
                            }
                        else:
                            error_text = await response.text()
                            logger.error(f"Queue API error: {response.status} - {error_text}")
                            return {
                                "success": False,
                                "error": f"Failed to join queue: {error_text}",
                                "message": "Sorry, there was an issue adding you to the queue. Please try again or contact staff."
                            }
            
            elif function_name == "get_queue_status":
                # Make actual API call to get queue status
                async with aiohttp.ClientSession() as session:
                    params = {
                        "phone": args["phone"],
                        "branch_id": args["branch_id"]
                    }
                    
                    async with session.get(f"{base_url}/queue-status", params=params) as response:
                        if response.status == 200:
                            result = await response.json()
                            return {
                                "success": True,
                                "queue_position": result.get("position", "Unknown"),
                                "estimated_wait_minutes": result.get("estimated_wait_minutes", 15),
                                "total_ahead": result.get("total_ahead", 0),
                                "branch_id": args["branch_id"]
                            }
                        else:
                            return {
                                "success": False,
                                "message": "Unable to find your queue status. Please check your phone number and branch."
                            }
            
            elif function_name == "reschedule_appointment":
                # Mock response for rescheduling (implement actual API later)
                return {
                    "success": True,
                    "message": f"Appointment rescheduled successfully",
                    "new_position": 7,
                    "new_wait_time": 30
                }
            
            elif function_name == "get_branch_info":
                return {
                    "branches": [
                        {
                            "branch_id": "main",
                            "name": "Main Hospital",
                            "address": "123 Medical Center Dr",
                            "services": self.medical_services[:8],  # Show first 8 services for clarity
                            "current_wait_times": {
                                "general": 20,
                                "cardiology": 45,
                                "ent": 25,
                                "orthopedics": 30,
                                "emergency": 5
                            }
                        }
                    ]
                }
            
            elif function_name == "cancel_appointment":
                return {
                    "success": True,
                    "message": "Appointment cancelled successfully",
                    "refund_info": "No cancellation fees applied"
                }
            
            else:
                return {"error": f"Unknown function: {function_name}"}

        except Exception as e:
            logger.error(f"Error executing function {function_name}: {str(e)}")
            return {"error": f"Failed to execute {function_name}: {str(e)}"}

    def detect_language(self, text: str) -> str:
        """Simple language detection based on common patterns"""
        # Hindi patterns
        hindi_chars = re.search(r'[\u0900-\u097F]', text)
        if hindi_chars:
            return "hi"
        
        # Spanish patterns  
        spanish_words = ['hola', 'gracias', 'por favor', 'ayuda', 'hospital', 'cita', 'doctor']
        if any(word in text.lower() for word in spanish_words):
            return "es"
            
        # Default to English
        return "en"

    def extract_patient_info(self, conversation: List[ConversationMessage]) -> PatientContext:
        """Extract patient information from conversation history"""
        context = PatientContext()
        
        for message in conversation:
            if message.role == "user":
                content = message.content.lower()
                
                # Extract phone number
                phone_pattern = r'\b(\+?[\d\s\-\(\)]{10,})\b'
                phone_match = re.search(phone_pattern, content)
                if phone_match and not context.phone:
                    context.phone = phone_match.group(1)
                
                # Extract name patterns
                name_patterns = [
                    r'my name is (\w+(?:\s+\w+)?)',
                    r'i am (\w+(?:\s+\w+)?)',
                    r'this is (\w+(?:\s+\w+)?)'
                ]
                for pattern in name_patterns:
                    name_match = re.search(pattern, content)
                    if name_match and not context.name:
                        context.name = name_match.group(1)
                        break
        
        return context

    async def cleanup_old_conversations(self, hours: int = 24):
        """Clean up conversations older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        sessions_to_remove = []
        for session_id, messages in self.conversations.items():
            if messages and messages[-1].timestamp < cutoff_time:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.conversations[session_id]
            if session_id in self.patient_contexts:
                del self.patient_contexts[session_id]
        
        logger.info(f"Cleaned up {len(sessions_to_remove)} old conversations")

    def get_fallback_response(self, user_message: str, session_id: str) -> str:
        """Provide fallback responses when Groq API is not available"""
        message_lower = user_message.lower()
        
        # Simple keyword-based responses
        if any(word in message_lower for word in ['join', 'book', 'appointment', 'queue']):
            return """I'd be happy to help you join the queue! However, I'm currently in limited mode. 
            
Please provide me with:
1. Your full name
2. Phone number
3. Which department you need (General, Cardiology, Orthopedics, etc.)
4. Preferred branch (Main, North, South, East)

I'll help you get added to the queue."""

        elif any(word in message_lower for word in ['status', 'position', 'wait', 'how long']):
            return """To check your queue position, I need your phone number and which branch you're registered at. 
            
Unfortunately, I'm currently in limited mode, so I recommend:
- Calling the hospital directly
- Asking staff at the reception desk
- Checking the display screens at your branch"""

        elif any(word in message_lower for word in ['emergency', 'urgent', 'chest pain', 'bleeding', 'difficulty breathing']):
            return """🚨 This sounds urgent! Please:

1. Call emergency services immediately: 911
2. Go to the nearest emergency room
3. Don't wait - seek immediate medical attention

For non-emergency situations, I can help you join the regular queue."""

        elif any(word in message_lower for word in ['reschedule', 'change', 'cancel']):
            return """I can help with rescheduling, but I'm currently in limited mode.

Please contact the hospital directly:
- Call the main number for appointment changes
- Visit the reception desk
- Use the hospital's patient portal if available

What specific changes do you need to make?"""

        elif any(word in message_lower for word in ['hello', 'hi', 'help', 'start']):
            return """Hello! I'm the QTrack AI Assistant. I'm currently running in limited mode, but I can still help you with:

📋 Basic queue information
🏥 Hospital services and branches  
📞 Contact information
🚨 Emergency guidance

What can I help you with today?"""

        else:
            return """I understand you need assistance, but I'm currently in limited mode due to a technical issue.

For immediate help, please:
- Contact hospital reception
- Call the main hospital number  
- Visit the information desk

Is this an emergency that needs immediate attention?"""