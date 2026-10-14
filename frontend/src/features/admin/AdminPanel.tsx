import React, { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { 
  Settings, 
  Edit3, 
  Trash2, 
  CheckCircle, 
  AlertTriangle,
  RefreshCw,
  User,
  Phone
} from 'lucide-react';
import { queueApi } from '../../api/queue';
import type { QueueResponse } from '../../types/queue';
import { getStatusColor, formatTime } from '../../lib/queueStatus';

interface AdminPanelProps {
  selectedBranch: string;
}

const AdminPanel: React.FC<AdminPanelProps> = ({ selectedBranch }) => {
  const [queueData, setQueueData] = useState<QueueResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [editingPatient, setEditingPatient] = useState<string | null>(null);
  const [newStatus, setNewStatus] = useState('');

  const statusOptions = [
    'waiting',
    'called', 
    'pending',
    'completed',
    'done'
  ];

  // Fetch queue data
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

  // Update patient status
  const updatePatientStatus = async (userId: string, status: string) => {
    try {
      await queueApi.updateStatus(userId, status);
      toast.success(`Status updated to ${status}`);
      setEditingPatient(null);
      fetchQueueData(); // Refresh data
    } catch (error: any) {
      console.error('Error updating status:', error);
      toast.error(error.response?.data?.detail || 'Failed to update status');
    }
  };

  // Remove patient from queue
  const removePatientFromQueue = async (userId: string, patientName: string) => {
    if (!window.confirm(`Are you sure you want to remove ${patientName} from the queue?`)) {
      return;
    }

    try {
      await queueApi.removeFromQueue(selectedBranch, userId);
      toast.success(`${patientName} removed from queue`);
      fetchQueueData(); // Refresh data
    } catch (error: any) {
      console.error('Error removing patient:', error);
      toast.error(error.response?.data?.detail || 'Failed to remove patient');
    }
  };

  // Remove patient log
  const removePatientLog = async (userId: string, patientName: string) => {
    if (!window.confirm(`Are you sure you want to remove ${patientName}'s log entry?`)) {
      return;
    }

    try {
      await queueApi.removeLog(userId, patientName);
      toast.success(`Log entry for ${patientName} removed`);
    } catch (error: any) {
      console.error('Error removing log:', error);
      toast.error(error.response?.data?.detail || 'Failed to remove log');
    }
  };

  // Start editing patient status
  const startEditing = (userId: string, currentStatus: string) => {
    setEditingPatient(userId);
    setNewStatus(currentStatus);
  };

  // Cancel editing
  const cancelEditing = () => {
    setEditingPatient(null);
    setNewStatus('');
  };

  // Save status changes
  const saveStatusChange = (userId: string) => {
    if (newStatus && newStatus !== '') {
      updatePatientStatus(userId, newStatus);
    }
  };

  useEffect(() => {
    fetchQueueData();
  }, [selectedBranch]);

  return (
    <div className="admin-panel-container">
      {/* Header */}
      <div className="admin-header">
        <div className="admin-title">
          <Settings className="header-icon" />
          <h2>Admin Panel - {selectedBranch}</h2>
        </div>
        <button 
          onClick={fetchQueueData}
          className="refresh-btn"
          disabled={isLoading}
        >
          <RefreshCw size={18} className={isLoading ? 'spinning' : ''} />
          Refresh
        </button>
      </div>

      {/* Quick Actions */}
      <div className="quick-actions">
        <div className="action-card">
          <h3>Quick Actions</h3>
          <div className="action-buttons">
            <button 
              onClick={fetchQueueData}
              className="action-btn primary"
            >
              <RefreshCw size={16} />
              Refresh Queue
            </button>
          </div>
        </div>

        <div className="stats-card">
          <h3>Queue Summary</h3>
          {queueData?.queue && (
            <div className="admin-stats">
              <div className="stat-item">
                <span>Total Patients:</span>
                <strong>{queueData.queue.length}</strong>
              </div>
              <div className="stat-item">
                <span>Waiting:</span>
                <strong>{queueData.queue.filter(p => p.status.toLowerCase() === 'waiting').length}</strong>
              </div>
              <div className="stat-item">
                <span>In Progress:</span>
                <strong>{queueData.queue.filter(p => ['called', 'pending'].includes(p.status.toLowerCase())).length}</strong>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Patient Management */}
      <div className="patient-management">
        <h3>Patient Management</h3>
        
        {isLoading && (
          <div className="loading-state">
            <RefreshCw className="spinning" />
            <p>Loading patients...</p>
          </div>
        )}

        {queueData?.message && !queueData.queue?.length && (
          <div className="empty-state">
            <AlertTriangle size={48} />
            <h3>No patients in queue</h3>
            <p>{queueData.message}</p>
          </div>
        )}

        {queueData?.queue && queueData.queue.length > 0 && (
          <div className="patients-table">
            <div className="table-header">
              <div className="col-name">Patient</div>
              <div className="col-status">Status</div>
              <div className="col-time">Joined At</div>
              <div className="col-actions">Actions</div>
            </div>

            {queueData.queue.map((patient) => (
              <div key={patient.user_id} className="table-row">
                <div className="col-name">
                  <div className="patient-info">
                    <User size={16} />
                    <div>
                      <div className="patient-name">{patient.name}</div>
                      <div className="patient-id">#{patient.user_id}</div>
                    </div>
                  </div>
                </div>

                <div className="col-status">
                  {editingPatient === patient.user_id ? (
                    <div className="status-editor">
                      <select 
                        value={newStatus}
                        onChange={(e) => setNewStatus(e.target.value)}
                        className="status-select"
                      >
                        {statusOptions.map(status => (
                          <option key={status} value={status}>
                            {status.charAt(0).toUpperCase() + status.slice(1)}
                          </option>
                        ))}
                      </select>
                      <div className="status-actions">
                        <button 
                          onClick={() => saveStatusChange(patient.user_id)}
                          className="save-btn"
                          title="Save"
                        >
                          <CheckCircle size={14} />
                        </button>
                        <button 
                          onClick={cancelEditing}
                          className="cancel-btn"
                          title="Cancel"
                        >
                          ×
                        </button>
                      </div>
                    </div>
                  ) : (
                    <span 
                      className="status-badge"
                      style={{ backgroundColor: getStatusColor(patient.status) }}
                    >
                      {patient.status}
                    </span>
                  )}
                </div>

                <div className="col-time">
                  {formatTime(patient.joined_at)}
                </div>

                <div className="col-actions">
                  <div className="action-buttons">
                    {editingPatient !== patient.user_id && (
                      <button
                        onClick={() => startEditing(patient.user_id, patient.status)}
                        className="edit-btn"
                        title="Edit Status"
                      >
                        <Edit3 size={14} />
                      </button>
                    )}
                    
                    <button
                      onClick={() => removePatientFromQueue(patient.user_id, patient.name)}
                      className="remove-btn"
                      title="Remove from Queue"
                    >
                      <Trash2 size={14} />
                    </button>

                    <button
                      onClick={() => removePatientLog(patient.user_id, patient.name)}
                      className="log-remove-btn"
                      title="Remove Log Entry"
                    >
                      <Phone size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer Info */}
      {queueData?.timestamp && (
        <div className="admin-footer">
          <p>Last updated: {new Date(queueData.timestamp).toLocaleString()}</p>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;