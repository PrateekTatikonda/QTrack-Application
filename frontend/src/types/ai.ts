export interface PatientContext {
  patient_id?: string;
  name?: string;
  phone?: string;
  branch_id?: string;
  queue_position?: number;
}

export interface ChatMessage {
  message: string;
  session_id?: string;
  language?: string;
  patient_context?: any;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  patient_context?: any;
  suggestions?: string[];
  detected_language?: string;
}

export interface ConversationHistory {
  session_id: string;
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
  }>;
}
