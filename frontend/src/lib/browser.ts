export const isMobileDevice = (): boolean => {
  return window.innerWidth <= 768 || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
};

export const getUserLanguage = (): string => {
  const browserLanguage = navigator.language || (navigator as any).userLanguage;

  if (browserLanguage.startsWith('es')) return 'es';
  if (browserLanguage.startsWith('hi')) return 'hi';

  return 'en';
};

export const speechSupport = {
  isSpeechRecognitionSupported: (): boolean => {
    return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
  },

  isSpeechSynthesisSupported: (): boolean => {
    return 'speechSynthesis' in window;
  },

  getAvailableVoices: (): SpeechSynthesisVoice[] => {
    return speechSynthesis.getVoices();
  },

  getVoiceForLanguage: (language: string): SpeechSynthesisVoice | null => {
    const voices = speechSynthesis.getVoices();
    const langCode = language === 'es' ? 'es' : language === 'hi' ? 'hi' : 'en';

    return voices.find(voice => voice.lang.startsWith(langCode)) || null;
  }
};
