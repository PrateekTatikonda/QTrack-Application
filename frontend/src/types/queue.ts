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
