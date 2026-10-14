import React, { useState } from 'react';
import { Toaster } from 'react-hot-toast';
import { Activity, Users, Clock, Settings, MessageCircle } from 'lucide-react';
// Global app styles must load before feature styles to keep the cascade order.
import './styles/app.css';
import JoinQueue from './features/queue/JoinQueue';
import QueueDisplay from './features/queue/QueueDisplay';
import AdminPanel from './features/admin/AdminPanel';
import { AIAssistant } from './features/ai-assistant/AIAssistant';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'join' | 'queue' | 'admin'>('join');
  const [selectedBranch, setSelectedBranch] = useState('ENT');
  const [showAIAssistant, setShowAIAssistant] = useState(false);

  const branches = ['ENT', 'CARDIO', 'ORTHO', 'NEURO', 'GENERAL'];

  return (
    <div className="app">
      <Toaster position="top-right" />
      
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <Activity className="logo-icon" />
            <h1>QTrack</h1>
            <span className="tagline">Real-time Queue Management</span>
          </div>
          
          <div className="branch-selector">
            <label htmlFor="branch">Branch:</label>
            <select 
              id="branch"
              value={selectedBranch} 
              onChange={(e) => setSelectedBranch(e.target.value)}
              className="branch-select"
            >
              {branches.map(branch => (
                <option key={branch} value={branch}>{branch}</option>
              ))}
            </select>
          </div>
          
          {/* AI Assistant Toggle */}
          <button
            onClick={() => setShowAIAssistant(!showAIAssistant)}
            className="ai-toggle-btn"
            title="AI Assistant"
          >
            <MessageCircle size={20} />
            <span>AI Help</span>
          </button>
        </div>
      </header>

      {/* Navigation */}
      <nav className="navigation">
        <button 
          className={`nav-btn ${activeTab === 'join' ? 'active' : ''}`}
          onClick={() => setActiveTab('join')}
        >
          <Users size={20} />
          Join Queue
        </button>
        <button 
          className={`nav-btn ${activeTab === 'queue' ? 'active' : ''}`}
          onClick={() => setActiveTab('queue')}
        >
          <Clock size={20} />
          Live Queue
        </button>
        <button 
          className={`nav-btn ${activeTab === 'admin' ? 'active' : ''}`}
          onClick={() => setActiveTab('admin')}
        >
          <Settings size={20} />
          Admin Panel
        </button>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        {activeTab === 'join' && (
          <JoinQueue 
            selectedBranch={selectedBranch} 
            onQueueJoin={() => setActiveTab('queue')}
          />
        )}
        {activeTab === 'queue' && (
          <QueueDisplay selectedBranch={selectedBranch} />
        )}
        {activeTab === 'admin' && (
          <AdminPanel selectedBranch={selectedBranch} />
        )}
      </main>
      
      {/* AI Assistant - Always show if enabled */}
      {showAIAssistant && (
        <AIAssistant 
          onClose={() => setShowAIAssistant(false)}
          initialContext={{
            branch_id: selectedBranch.toLowerCase()
          }}
          language="en"
        />
      )}
    </div>
  );
};

export default App;
