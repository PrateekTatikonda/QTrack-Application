import React, { useState } from 'react';
import { toast } from 'react-hot-toast';
import { UserPlus, Phone, User } from 'lucide-react';
import { queueApi } from '../../api/queue';
import type { JoinQueueRequest } from '../../types/queue';

interface JoinQueueProps {
  selectedBranch: string;
  onQueueJoin: () => void;
}

const JoinQueue: React.FC<JoinQueueProps> = ({ selectedBranch, onQueueJoin }) => {
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
  });
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim() || !formData.phone.trim()) {
      toast.error('Please fill in all fields');
      return;
    }

    if (formData.phone.length < 10) {
      toast.error('Please enter a valid phone number');
      return;
    }

    setIsLoading(true);
    
    try {
      const requestData: JoinQueueRequest = {
        name: formData.name.trim(),
        phone: formData.phone.trim(),
        branch_id: selectedBranch,
        service_type: selectedBranch.toLowerCase(),
      };

      const response = await queueApi.joinQueue(requestData);
      
      toast.success(`Welcome ${formData.name}! You've joined the ${selectedBranch} queue.`);
      toast.success(`Your token: ${response.user_id}`);
      
      // Reset form
      setFormData({ name: '', phone: '' });
      
      // Navigate to queue view
      onQueueJoin();
      
    } catch (error: any) {
      console.error('Error joining queue:', error);
      toast.error(error.response?.data?.detail || 'Failed to join queue');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  return (
    <div className="join-queue-container">
      <div className="join-queue-card">
        <div className="card-header">
          <UserPlus className="header-icon" />
          <h2>Join Queue - {selectedBranch}</h2>
          <p>Enter your details to join the queue</p>
        </div>

        <form onSubmit={handleSubmit} className="join-form">
          <div className="form-group">
            <label htmlFor="name">
              <User size={18} />
              Full Name
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="Enter your full name"
              required
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="phone">
              <Phone size={18} />
              Phone Number
            </label>
            <input
              type="tel"
              id="phone"
              name="phone"
              value={formData.phone}
              onChange={handleInputChange}
              placeholder="Enter your phone number"
              required
              disabled={isLoading}
            />
          </div>

          <div className="branch-info">
            <strong>Selected Branch: {selectedBranch}</strong>
          </div>

          <button 
            type="submit" 
            className="join-btn"
            disabled={isLoading || !formData.name.trim() || !formData.phone.trim()}
          >
            {isLoading ? (
              <>
                <div className="spinner"></div>
                Joining Queue...
              </>
            ) : (
              <>
                <UserPlus size={20} />
                Join Queue
              </>
            )}
          </button>
        </form>

        <div className="info-section">
          <h3>What happens next?</h3>
          <ul>
            <li>You'll receive a unique token ID</li>
            <li>Monitor your queue position in real-time</li>
            <li>Get notified when it's your turn</li>
            <li>Average wait time varies by branch</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default JoinQueue;