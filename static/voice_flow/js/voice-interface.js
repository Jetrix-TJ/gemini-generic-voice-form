/**
 * Voice Interface WebSocket Client
 * Handles real-time voice conversation with AI
 */

class VoiceInterface {
    constructor(sessionId, wsScheme, wsHost, totalFields) {
        this.sessionId = sessionId;
        this.wsUrl = `${wsScheme}://${wsHost}/ws/voice/${sessionId}/`;
        this.totalFields = totalFields;
        this.ws = null;
        this.isRecording = false;
        this.recognition = null;
        this.currentField = null;
        this.fieldsCompleted = 0;
        
        // UI Elements
        this.micButton = document.getElementById('mic-button');
        this.micIcon = document.getElementById('mic-icon');
        this.recordingRing = document.getElementById('recording-ring');
        this.statusText = document.getElementById('status-text');
        this.connectionStatus = document.getElementById('connection-status');
        this.aiMessage = document.getElementById('ai-message');
        this.aiMessageText = document.getElementById('ai-message-text');
        this.userInput = document.getElementById('user-input');
        this.userInputText = document.getElementById('user-input-text');
        this.textInput = document.getElementById('text-input');
        this.sendButton = document.getElementById('send-button');
        this.skipButton = document.getElementById('skip-button');
        this.fieldInfo = document.getElementById('field-info');
        this.fieldName = document.getElementById('field-name');
        this.fieldType = document.getElementById('field-type');
        this.progressBar = document.getElementById('progress-bar');
        this.progressText = document.getElementById('progress-text');
        this.conversationHistory = document.getElementById('conversation-history');
        this.completionModal = document.getElementById('completion-modal');
        this.completionMessage = document.getElementById('completion-message');
        
        this.init();
    }
    
    init() {
        // Initialize WebSocket
        this.connectWebSocket();
        
        // Initialize Speech Recognition
        this.initSpeechRecognition();
        
        // Set up event listeners
        this.micButton.addEventListener('click', () => this.toggleRecording());
        this.sendButton.addEventListener('click', () => this.sendTextInput());
        this.textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendTextInput();
        });
        this.skipButton.addEventListener('click', () => this.skipField());
    }
    
    connectWebSocket() {
        this.updateConnectionStatus('Connecting...', 'text-yellow-500');
        
        this.ws = new WebSocket(this.wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus('Connected', 'text-green-500');
            this.enableControls();
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('Connection Error', 'text-red-500');
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket closed');
            this.updateConnectionStatus('Disconnected', 'text-red-500');
            this.disableControls();
            
            // Attempt to reconnect after 3 seconds
            setTimeout(() => {
                if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
                    this.connectWebSocket();
                }
            }, 3000);
        };
    }
    
    initSpeechRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US';
            
            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                console.log('Speech recognized:', transcript);
                this.sendMessage('text', transcript);
                this.displayUserMessage(transcript);
            };
            
            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.stopRecording();
                
                if (event.error === 'no-speech') {
                    this.updateStatus('No speech detected. Please try again.');
                } else if (event.error === 'not-allowed') {
                    this.updateStatus('Microphone access denied. Please use text input.');
                } else {
                    this.updateStatus('Speech recognition error. Please try again.');
                }
            };
            
            this.recognition.onend = () => {
                this.stopRecording();
            };
        } else {
            console.warn('Speech recognition not supported');
            this.micButton.disabled = true;
            this.updateStatus('Voice input not supported. Please use text input.');
        }
    }
    
    handleMessage(data) {
        console.log('Received message:', data);
        
        switch (data.type) {
            case 'greeting':
                this.displayAIMessage(data.message);
                this.updateStatus('Ready to start. Click the microphone or type your response.');
                this.addToConversation('AI', data.message);
                break;
                
            case 'field_prompt':
                this.currentField = data.field;
                this.displayAIMessage(data.ai_prompt);
                this.updateFieldInfo(data.field);
                this.updateStatus('Listening... Speak your answer or type it below.');
                this.addToConversation('AI', data.ai_prompt);
                break;
                
            case 'field_completed':
                this.displayAIMessage(data.ai_response);
                this.updateProgress(data.progress);
                this.addToConversation('AI', data.ai_response);
                this.fieldsCompleted++;
                break;
                
            case 'next_field':
                this.currentField = data.field;
                this.displayAIMessage(data.ai_prompt);
                this.updateFieldInfo(data.field);
                this.addToConversation('AI', data.ai_prompt);
                break;
                
            case 'field_retry':
                this.displayAIMessage(data.ai_response);
                this.addToConversation('AI', data.ai_response);
                this.updateStatus('Please try again.');
                break;
                
            case 'completed':
                this.handleCompletion(data);
                break;
                
            case 'error':
                this.displayError(data.message);
                break;
                
            default:
                console.warn('Unknown message type:', data.type);
        }
    }
    
    sendMessage(type, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: type,
                data: data,
                field_name: this.currentField?.name
            }));
        }
    }
    
    toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            this.startRecording();
        }
    }
    
    startRecording() {
        if (!this.recognition) {
            this.updateStatus('Voice input not available. Please use text input.');
            return;
        }
        
        this.isRecording = true;
        this.micButton.classList.add('recording', 'bg-red-600');
        this.recordingRing.classList.remove('hidden');
        this.updateStatus('Listening... Speak now.');
        
        try {
            this.recognition.start();
        } catch (error) {
            console.error('Error starting recognition:', error);
            this.stopRecording();
        }
    }
    
    stopRecording() {
        this.isRecording = false;
        this.micButton.classList.remove('recording', 'bg-red-600');
        this.recordingRing.classList.add('hidden');
        
        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (error) {
                console.error('Error stopping recognition:', error);
            }
        }
    }
    
    sendTextInput() {
        const text = this.textInput.value.trim();
        if (text) {
            this.sendMessage('text', text);
            this.displayUserMessage(text);
            this.textInput.value = '';
        }
    }
    
    skipField() {
        if (this.currentField && !this.currentField.required) {
            this.sendMessage('skip_field', null);
        }
    }
    
    updateStatus(text) {
        this.statusText.textContent = text;
    }
    
    updateConnectionStatus(text, colorClass) {
        this.connectionStatus.textContent = text;
        this.connectionStatus.className = `text-sm mt-2 ${colorClass}`;
    }
    
    displayAIMessage(message) {
        this.aiMessageText.textContent = message;
        this.aiMessage.classList.remove('hidden');
        this.userInput.classList.add('hidden');
        
        // Speak the message if speech synthesis is available
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(message);
            utterance.rate = 0.9;
            utterance.pitch = 1.0;
            speechSynthesis.speak(utterance);
        }
    }
    
    displayUserMessage(message) {
        this.userInputText.textContent = message;
        this.userInput.classList.remove('hidden');
        this.aiMessage.classList.add('hidden');
    }
    
    displayError(message) {
        this.updateStatus(`Error: ${message}`);
        alert(message);
    }
    
    updateFieldInfo(field) {
        this.currentField = field;
        this.fieldName.textContent = field.name.replace(/_/g, ' ').toUpperCase();
        this.fieldType.textContent = `Type: ${field.type} ${field.required ? '(Required)' : '(Optional)'}`;
        this.fieldInfo.classList.remove('hidden');
        
        // Show skip button for optional fields
        if (!field.required) {
            this.skipButton.classList.remove('hidden');
        } else {
            this.skipButton.classList.add('hidden');
        }
    }
    
    updateProgress(progress) {
        this.fieldsCompleted = progress.fields_completed;
        const percentage = progress.percentage;
        this.progressBar.style.width = `${percentage}%`;
        this.progressText.textContent = `${progress.fields_completed} of ${progress.total_fields} fields completed`;
    }
    
    addToConversation(role, message) {
        // Clear "no messages" text if present
        if (this.conversationHistory.children.length === 1 && 
            this.conversationHistory.children[0].textContent === 'No messages yet...') {
            this.conversationHistory.innerHTML = '';
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `p-4 rounded-lg ${role === 'AI' ? 'bg-indigo-50' : 'bg-gray-50'}`;
        
        const roleSpan = document.createElement('span');
        roleSpan.className = 'font-semibold text-sm';
        roleSpan.textContent = `${role}: `;
        
        const contentSpan = document.createElement('span');
        contentSpan.className = 'text-gray-700';
        contentSpan.textContent = message;
        
        messageDiv.appendChild(roleSpan);
        messageDiv.appendChild(contentSpan);
        
        this.conversationHistory.appendChild(messageDiv);
        this.conversationHistory.scrollTop = this.conversationHistory.scrollHeight;
    }
    
    handleCompletion(data) {
        this.completionMessage.textContent = data.message;
        this.completionModal.classList.remove('hidden');
        this.disableControls();
        
        // Update progress to 100%
        this.progressBar.style.width = '100%';
        this.progressText.textContent = `${this.totalFields} of ${this.totalFields} fields completed`;
        
        this.addToConversation('System', 'Form completed successfully! 🎉');
    }
    
    enableControls() {
        this.micButton.disabled = false;
        this.textInput.disabled = false;
        this.sendButton.disabled = false;
    }
    
    disableControls() {
        this.micButton.disabled = true;
        this.textInput.disabled = true;
        this.sendButton.disabled = true;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new VoiceInterface(sessionId, wsScheme, wsHost, totalFields);
});

