import apiClient from './client';
import { API_BASE_URL } from '../config/env';
import type { JoinQueueRequest, QueueResponse } from '../types/queue';

export const queueApi = {
  joinQueue: async (data: JoinQueueRequest) => {
    const response = await apiClient.post('/join-queue', data);
    return response.data;
  },

  getLiveQueue: async (branchId: string): Promise<QueueResponse> => {
    const response = await apiClient.get(`/live-queue/${branchId}`);
    return response.data;
  },

  updateStatus: async (userId: string, newStatus: string) => {
    const response = await apiClient.put('/update-status', {
      user_id: userId,
      new_status: newStatus,
    });
    return response.data;
  },

  removeFromQueue: async (branchId: string, userId: string) => {
    const response = await apiClient.delete('/remove-from-queue', {
      params: { branch_id: branchId, user_id: userId },
    });
    return response.data;
  },

  removeLog: async (userId: string, name?: string) => {
    const response = await apiClient.delete('/remove-log', {
      params: { user_id: userId, ...(name && { name }) },
    });
    return response.data;
  },

  healthCheck: async () => {
    const response = await apiClient.get('/health-check');
    return response.data;
  },
};

// SSE event source for real-time queue updates
export const createSSEConnection = (branchId: string, onMessage: (data: QueueResponse) => void) => {
  const eventSource = new EventSource(`${API_BASE_URL}/live-queue-stream/${branchId}`);

  eventSource.onmessage = (event) => {
    try {
      let rawData = event.data;

      if (typeof rawData === 'string') {
        if (rawData.startsWith('data: ')) {
          rawData = rawData.substring(6);
        }

        if (rawData.trim() === '' || rawData.includes('heartbeat') || rawData.includes('ping')) {
          return;
        }

        const data = JSON.parse(rawData);
        onMessage(data);
      }
    } catch (error) {
      console.error('Error parsing SSE data:', error, 'Raw data:', event.data);
    }
  };

  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error);
  };

  return eventSource;
};
