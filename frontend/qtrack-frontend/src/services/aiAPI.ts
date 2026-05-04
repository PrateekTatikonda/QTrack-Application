/**
 * API service for AI Agent communication
 * Extends existing API service to include AI functionality
 */

// Extend the existing API service
const API_BASE_URL = 'http://localhost:8000';

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

// AI Agent API functions
export const aiAPI = {
  /**
   * Send a chat message to the AI agent
   */
  async sendMessage(chatData: ChatMessage): Promise<ChatResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/ai/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(chatData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error sending message to AI:', error);
      throw new Error('Failed to communicate with AI assistant');
    }
  },

  /**
   * Get conversation history for a session
   */
  async getConversationHistory(sessionId: string): Promise<ConversationHistory> {
    try {
      const response = await fetch(`${API_BASE_URL}/ai/conversation/${sessionId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching conversation history:', error);
      throw new Error('Failed to fetch conversation history');
    }
  },

  /**
   * Clear conversation history for a session
   */
  async clearConversation(sessionId: string): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/ai/conversation/${sessionId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } catch (error) {
      console.error('Error clearing conversation:', error);
      throw new Error('Failed to clear conversation');
    }
  },

  /**
   * Check AI agent health
   */
  async checkHealth(): Promise<any> {
    try {
      const response = await fetch(`${API_BASE_URL}/ai/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error checking AI health:', error);
      throw new Error('Failed to check AI agent status');
    }
  },
};

// Helper function to detect if user is on mobile
export const isMobileDevice = (): boolean => {
  return window.innerWidth <= 768 || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
};

// Helper function to get user's preferred language
export const getUserLanguage = (): string => {
  const browserLanguage = navigator.language || (navigator as any).userLanguage;
  
  // Map common language codes to supported languages
  if (browserLanguage.startsWith('es')) return 'es';
  if (browserLanguage.startsWith('hi')) return 'hi';
  
  return 'en'; // Default to English
};

// Helper function for voice/speech features
export const speechSupport = {
  isSpeechRecognitionSupported: (): boolean => {
    return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
  },

  isSpeechSynthesisSupported: (): boolean => {
    return 'speechSynthesis' in window;
  },

  getAvailableVoices: (): SpeechSynthesisVoice[] => {
    return speechSynthesis.getVoices();
  },

  getVoiceForLanguage: (language: string): SpeechSynthesisVoice | null => {
    const voices = speechSynthesis.getVoices();
    const langCode = language === 'es' ? 'es' : language === 'hi' ? 'hi' : 'en';
    
    return voices.find(voice => voice.lang.startsWith(langCode)) || null;
  }
};

export default aiAPI;