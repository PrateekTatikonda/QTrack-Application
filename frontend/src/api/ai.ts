import { API_BASE_URL } from '../config/env';
import type { ChatMessage, ChatResponse, ConversationHistory } from '../types/ai';

export const aiApi = {
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
