import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface JoinQueueRequest {
  name: string;
  phone: string;
  branch_id: string;
  service_type: string;
}

export interface Patient {
  user_id: string;
  name: string;
  status: string;
  joined_at: string;
}

export interface QueueResponse {
  branch_id: string;
  queue: Patient[];
  message?: string;
  timestamp?: string;
}

export interface UpdateStatusRequest {
  user_id: string;
  new_status: string;
}

// API Functions
export const apiService = {
  // Join Queue
  joinQueue: async (data: JoinQueueRequest) => {
    const response = await api.post('/join-queue', data);
    return response.data;
  },

  // Get Live Queue
  getLiveQueue: async (branchId: string): Promise<QueueResponse> => {
    const response = await api.get(`/live-queue/${branchId}`);
    return response.data;
  },

  // Update Status
  updateStatus: async (userId: string, newStatus: string) => {
    const response = await api.put('/update-status', {
      user_id: userId,
      new_status: newStatus,
    });
    return response.data;
  },

  // Remove from Queue
  removeFromQueue: async (branchId: string, userId: string) => {
    const response = await api.delete('/remove-from-queue', {
      params: { branch_id: branchId, user_id: userId },
    });
    return response.data;
  },

  // Remove Log
  removeLog: async (userId: string, name?: string) => {
    const response = await api.delete('/remove-log', {
      params: { user_id: userId, ...(name && { name }) },
    });
    return response.data;
  },

  // Health Check
  healthCheck: async () => {
    const response = await api.get('/health-check');
    return response.data;
  },
};

// SSE Event Source for real-time updates
export const createSSEConnection = (branchId: string, onMessage: (data: QueueResponse) => void) => {
  const eventSource = new EventSource(`${API_BASE_URL}/live-queue-stream/${branchId}`);
  
  eventSource.onmessage = (event) => {
    try {
      let rawData = event.data;
      
      // Handle different SSE data formats
      if (typeof rawData === 'string') {
        // Remove "data: " prefix if present
        if (rawData.startsWith('data: ')) {
          rawData = rawData.substring(6);
        }
        
        // Skip heartbeat messages
        if (rawData.trim() === '' || rawData.includes('heartbeat') || rawData.includes('ping')) {
          return;
        }
        
        // Parse JSON data
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

export default api;