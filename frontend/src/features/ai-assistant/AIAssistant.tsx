import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, MicOff, MessageCircle, X, Volume2, VolumeX } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { aiApi } from '../../api/ai';
import type { PatientContext } from '../../types/ai';
import './AIAssistant.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  suggestions?: string[];
}

interface AIAssistantProps {
  onClose?: () => void;
  initialContext?: PatientContext;
  language?: string;
}

export const AIAssistant: React.FC<AIAssistantProps> = ({ 
  onClose, 
  initialContext,
  language = 'en' 
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [patientContext, setPatientContext] = useState<PatientContext | undefined>(initialContext);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);

  // Initialize speech recognition and synthesis
  useEffect(() => {
    // Speech Recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.lang = getLanguageCode(language);

      recognitionRef.current.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputMessage(transcript);
        setIsListening(false);
      };

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
        toast.error('Speech recognition failed');
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }

    // Speech Synthesis
    if ('speechSynthesis' in window) {
      synthRef.current = window.speechSynthesis;
    }

    // Initial greeting
    addWelcomeMessage();
  }, [language]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const getLanguageCode = (lang: string) => {
    const langMap: Record<string, string> = {
      'en': 'en-US',
      'es': 'es-ES',
      'hi': 'hi-IN'
    };
    return langMap[lang] || 'en-US';
  };

  const addWelcomeMessage = () => {
    const welcomeMessages = {
      en: "Hello! I'm your QTrack AI Assistant. I can help you join queues, check your position, reschedule appointments, and answer questions about our hospital services. How can I assist you today?",
      es: "¡Hola! Soy tu Asistente de IA QTrack. Puedo ayudarte a unirte a colas, verificar tu posición, reprogramar citas y responder preguntas sobre nuestros servicios hospitalarios. ¿Cómo puedo ayudarte hoy?",
      hi: "नमस्ते! मैं आपका QTrack AI असिस्टेंट हूँ। मैं आपको कतार में शामिल होने, अपनी स्थिति जाँचने, अपॉइंटमेंट रीशेड्यूल करने और हमारी अस्पताल सेवाओं के बारे में प्रश्नों का उत्तर देने में मदद कर सकता हूँ।"
    };

    const welcomeMessage: Message = {
      role: 'assistant',
      content: welcomeMessages[language as keyof typeof welcomeMessages] || welcomeMessages.en,
      timestamp: new Date().toISOString(),
      suggestions: [
        'Join queue',
        'Check my position', 
        'Hospital services',
        'Emergency help'
      ]
    };

    setMessages([welcomeMessage]);
  };

  const sendMessage = async (messageText?: string) => {
    const textToSend = messageText || inputMessage.trim();
    if (!textToSend) return;

    // Add user message
    const userMessage: Message = {
      role: 'user',
      content: textToSend,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const data = await aiApi.sendMessage({
        message: textToSend,
        session_id: sessionId || undefined,
        language: language,
        patient_context: patientContext
      });
      
      // Update session ID if new
      if (data.session_id && !sessionId) {
        setSessionId(data.session_id);
      }

      // Update patient context if provided
      if (data.patient_context) {
        setPatientContext(data.patient_context);
      }

      // Add AI response
      const aiMessage: Message = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString(),
        suggestions: data.suggestions
      };

      setMessages(prev => [...prev, aiMessage]);

      // Speak the response if text-to-speech is available
      if (synthRef.current && !isSpeaking) {
        speakMessage(data.response);
      }

    } catch (error) {
      console.error('Error sending message:', error);
      toast.error('Failed to send message');
      
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again or contact hospital staff for assistance.',
        timestamp: new Date().toISOString()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      setIsListening(true);
      recognitionRef.current.start();
    }
  };

  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    }
  };

  const speakMessage = (text: string) => {
    if (synthRef.current && !isSpeaking) {
      setIsSpeaking(true);
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = getLanguageCode(language);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      
      utterance.onend = () => {
        setIsSpeaking(false);
      };
      
      utterance.onerror = () => {
        setIsSpeaking(false);
      };

      synthRef.current.speak(utterance);
    }
  };

  const stopSpeaking = () => {
    if (synthRef.current) {
      synthRef.current.cancel();
      setIsSpeaking(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (isMinimized) {
    return (
      <div className="ai-assistant-minimized" onClick={() => setIsMinimized(false)}>
        <MessageCircle className="w-6 h-6" />
        <span>AI Assistant</span>
        {messages.length > 1 && (
          <div className="notification-badge">
            {messages.filter(m => m.role === 'assistant').length}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="ai-assistant">
      <div className="ai-assistant-header">
        <div className="header-title">
          <MessageCircle className="w-5 h-5" />
          <h3>QTrack AI Assistant</h3>
        </div>
        <div className="header-controls">
          <button 
            onClick={isSpeaking ? stopSpeaking : undefined}
            className={`control-btn ${isSpeaking ? 'speaking' : ''}`}
            disabled={!isSpeaking}
          >
            {isSpeaking ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
          <button onClick={() => setIsMinimized(true)} className="control-btn">
            <span>−</span>
          </button>
          {onClose && (
            <button onClick={onClose} className="control-btn close-btn">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="ai-assistant-messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <div className="message-content">
              <div className="message-text">{message.content}</div>
              <div className="message-time">
                {new Date(message.timestamp).toLocaleTimeString()}
              </div>
            </div>
            
            {message.suggestions && message.suggestions.length > 0 && (
              <div className="message-suggestions">
                {message.suggestions.map((suggestion, idx) => (
                  <button
                    key={idx}
                    className="suggestion-chip"
                    onClick={() => sendMessage(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        
        {isLoading && (
          <div className="message assistant">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="ai-assistant-input">
        <div className="input-container">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              language === 'es' ? 'Escribe tu mensaje...' :
              language === 'hi' ? 'अपना संदेश टाइप करें...' :
              'Type your message...'
            }
            disabled={isLoading}
            rows={1}
          />
          
          <div className="input-controls">
            {recognitionRef.current && (
              <button
                onClick={isListening ? stopListening : startListening}
                className={`voice-btn ${isListening ? 'listening' : ''}`}
                disabled={isLoading}
              >
                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
            )}
            
            <button
              onClick={() => sendMessage()}
              className="send-btn"
              disabled={isLoading || !inputMessage.trim()}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
