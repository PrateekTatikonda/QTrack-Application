import React, { useState, useEffect, useRef } from 'react';
import { toast } from 'react-hot-toast';
import { 
  Clock, 
  Users, 
  RefreshCw, 
  Eye, 
  EyeOff, 
  AlertCircle,
  CheckCircle,
  XCircle,
  Timer
} from 'lucide-react';
import { queueApi, createSSEConnection } from '../../api/queue';
import type { QueueResponse, Patient } from '../../types/queue';
import { getStatusColor, formatTime } from '../../lib/queueStatus';

interface QueueDisplayProps {
  selectedBranch: string;
}

const QueueDisplay: React.FC<QueueDisplayProps> = ({ selectedBranch }) => {
  const [queueData, setQueueData] = useState<QueueResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Status icon mapping
  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'waiting': return <Timer size={16} />;
      case 'called': return <AlertCircle size={16} />;
      case 'completed': 
      case 'done': return <CheckCircle size={16} />;
      case 'pending': return <Clock size={16} />;
      default: return <XCircle size={16} />;
    }
  };

  // Fetch queue data manually
  const fetchQueueData = async () => {
    setIsLoading(true);
    try {
      const data = await queueApi.getLiveQueue(selectedBranch);
      setQueueData(data);
    } catch (error: any) {
      console.error('Error fetching queue data:', error);
      toast.error('Failed to fetch queue data');
    } finally {
      setIsLoading(false);
    }
  };

  // Setup SSE connection for real-time updates
  const setupSSEConnection = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = createSSEConnection(selectedBranch, (data: QueueResponse) => {
      setQueueData(data);
      setIsConnected(true);
    });

    eventSource.onopen = () => {
      setIsConnected(true);
      toast.success('Connected to live updates');
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      toast.error('Lost connection to live updates');
    };

    eventSourceRef.current = eventSource;
  };

  // Toggle auto-refresh (SSE connection)
  const toggleAutoRefresh = () => {
    if (autoRefresh) {
      // Disconnect SSE
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsConnected(false);
      setAutoRefresh(false);
      toast.success('Auto-refresh disabled');
    } else {
      // Connect SSE
      setupSSEConnection();
      setAutoRefresh(true);
    }
  };

  // Calculate queue statistics
  const getQueueStats = (queue: Patient[]) => {
    const total = queue.length;
    const waiting = queue.filter(p => p.status.toLowerCase() === 'waiting').length;
    const called = queue.filter(p => p.status.toLowerCase() === 'called').length;
    const completed = queue.filter(p => ['completed', 'done'].includes(p.status.toLowerCase())).length;

    return { total, waiting, called, completed };
  };

  // Calculate position in queue (only for waiting patients)
  const getQueuePosition = (patient: Patient, queue: Patient[]) => {
    const waitingQueue = queue.filter(p => p.status.toLowerCase() === 'waiting');
    const position = waitingQueue.findIndex(p => p.user_id === patient.user_id);
    return position >= 0 ? position + 1 : null;
  };

  useEffect(() => {
    // Initial fetch
    fetchQueueData();

    // Setup SSE if auto-refresh is enabled
    if (autoRefresh) {
      setupSSEConnection();
    }

    // Cleanup on unmount or branch change
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [selectedBranch]);

  const stats = queueData?.queue ? getQueueStats(queueData.queue) : { total: 0, waiting: 0, called: 0, completed: 0 };

  return (
    <div className="queue-display-container">
      {/* Header Controls */}
      <div className="queue-header">
        <div className="queue-title">
          <Users className="header-icon" />
          <h2>Live Queue - {selectedBranch}</h2>
          <div className="connection-status">
            {isConnected ? (
              <span className="connected">🟢 Live</span>
            ) : (
              <span className="disconnected">🔴 Offline</span>
            )}
          </div>
        </div>

        <div className="queue-controls">
          <button 
            onClick={toggleAutoRefresh}
            className={`refresh-btn ${autoRefresh ? 'active' : ''}`}
            title={autoRefresh ? 'Disable auto-refresh' : 'Enable auto-refresh'}
          >
            {autoRefresh ? <EyeOff size={18} /> : <Eye size={18} />}
            {autoRefresh ? 'Live' : 'Manual'}
          </button>

          <button 
            onClick={fetchQueueData}
            className="manual-refresh-btn"
            disabled={isLoading}
            title="Refresh manually"
          >
            <RefreshCw size={18} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {/* Queue Statistics */}
      <div className="queue-stats">
        <div className="stat-card total">
          <div className="stat-number">{stats.total}</div>
          <div className="stat-label">Total Patients</div>
        </div>
        <div className="stat-card waiting">
          <div className="stat-number">{stats.waiting}</div>
          <div className="stat-label">Waiting</div>
        </div>
        <div className="stat-card called">
          <div className="stat-number">{stats.called}</div>
          <div className="stat-label">Called</div>
        </div>
        <div className="stat-card completed">
          <div className="stat-number">{stats.completed}</div>
          <div className="stat-label">Completed</div>
        </div>
      </div>

      {/* Queue List */}
      <div className="queue-list">
        {isLoading && !queueData && (
          <div className="loading-state">
            <RefreshCw className="spinning" />
            <p>Loading queue data...</p>
          </div>
        )}

        {queueData?.message && !queueData.queue?.length && (
          <div className="empty-state">
            <Users size={48} />
            <h3>No patients in queue</h3>
            <p>{queueData.message}</p>
          </div>
        )}

        {queueData?.queue && queueData.queue.length > 0 && (
          <>
            <div className="queue-list-header">
              <h3>Current Queue ({queueData.queue.length} patients)</h3>
              {queueData.timestamp && (
                <span className="last-updated">
                  Last updated: {formatTime(queueData.timestamp)}
                </span>
              )}
            </div>

            <div className="patients-grid">
              {queueData.queue.map((patient, index) => {
                const position = getQueuePosition(patient, queueData.queue);
                return (
                  <div 
                    key={patient.user_id} 
                    className={`patient-card ${patient.status.toLowerCase()}`}
                  >
                    <div className="patient-header">
                      <div className="patient-info">
                        <span className="patient-name">{patient.name}</span>
                        <span className="patient-id">#{patient.user_id}</span>
                      </div>
                      <div 
                        className="status-badge"
                        style={{ backgroundColor: getStatusColor(patient.status) }}
                      >
                        {getStatusIcon(patient.status)}
                        {patient.status}
                      </div>
                    </div>

                    <div className="patient-details">
                      <div className="detail-item">
                        <Clock size={14} />
                        <span>Joined: {formatTime(patient.joined_at)}</span>
                      </div>
                      {position && (
                        <div className="detail-item">
                          <Users size={14} />
                          <span>Position: #{position}</span>
                        </div>
                      )}
                      <div className="detail-item">
                        <span className="queue-number">Queue #{index + 1}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {queueData?.timestamp && (
        <div className="queue-footer">
          <p>Data refreshed at: {new Date(queueData.timestamp).toLocaleString()}</p>
        </div>
      )}
    </div>
  );
};

export default QueueDisplay;