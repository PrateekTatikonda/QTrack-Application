export const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case 'waiting': return '#f59e0b';
    case 'called': return '#3b82f6';
    case 'completed':
    case 'done': return '#10b981';
    case 'pending': return '#8b5cf6';
    default: return '#6b7280';
  }
};

export const formatTime = (timestamp: string) => {
  if (timestamp === 'Unknown') return 'Unknown';
  try {
    return new Date(timestamp).toLocaleTimeString();
  } catch {
    return 'Unknown';
  }
};
