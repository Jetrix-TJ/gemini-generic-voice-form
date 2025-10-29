/**
 * Live API Voice Interface with Bidirectional Audio Streaming
 * Based on Gemini 2.5 Flash Native Audio Live API
 */

class LiveAudioInterface {
    constructor(sessionId, wsScheme, wsHost) {
        this.sessionId = sessionId;
        this.wsUrl = `${wsScheme}://${wsHost}/ws/live/${sessionId}/`;
        this.ws = null;
        this.audioContext = null;
        this.mediaStream = null;
        this.audioWorkletNode = null;
        this.isRecording = false;
        this.isPlaying = false;
        this.audioQueue = [];
        this.isPlayingQueue = false;
        
        // Note: Speech recognition disabled - conflicts with audio streaming
        // Live API is audio-only for maximum speed
        
        // Audio configuration matching Gemini Live API
        this.SEND_SAMPLE_RATE = 16000;  // Browser → Gemini
        this.RECEIVE_SAMPLE_RATE = 24000;  // Gemini → Browser
        this.CHANNELS = 1;  // Mono
        
        // UI Elements
        this.micButton = document.getElementById('mic-button');
        this.statusText = document.getElementById('status-text');
        this.connectionStatus = document.getElementById('connection-status');
        this.progressBar = document.getElementById('progress-bar');
        this.progressText = document.getElementById('progress-text');
        this.conversationHistory = document.getElementById('conversation-history');
        
        this.init();
    }
    
    async init() {
        // Initialize Audio Context
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: this.SEND_SAMPLE_RATE
        });
        
        console.log('Audio context created:', this.audioContext.state, 'Sample rate:', this.audioContext.sampleRate);
        
        // Connect WebSocket
        this.connectWebSocket();
        
        // Set up event listeners
        this.micButton.addEventListener('click', () => {
            console.log('Microphone button clicked');
            this.toggleRecording();
        });
        
        // Complete button
        const completeButton = document.getElementById('complete-button');
        if (completeButton) {
            completeButton.addEventListener('click', () => {
                console.log('Manual completion clicked');
                this.ws.send(JSON.stringify({ type: 'manual_complete' }));
                completeButton.style.display = 'none';
            });
            
            // Show complete button after 10 seconds
            setTimeout(() => {
                completeButton.style.display = 'block';
            }, 10000);
        }
    }
    
    connectWebSocket() {
        this.updateConnectionStatus('Connecting...', 'text-yellow-500');
        
        this.ws = new WebSocket(this.wsUrl);
        this.ws.binaryType = 'arraybuffer';
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus('Connected to Live API', 'text-green-500');
            this.ws.send(JSON.stringify({type: 'start'}));
            
            // Request microphone permission immediately
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    console.log('Microphone permission granted');
                    // Stop the stream - we'll start it when user clicks mic
                    stream.getTracks().forEach(track => track.stop());
                })
                .catch(err => {
                    console.error('Microphone permission denied:', err);
                    this.showError('Microphone access required. Please grant permission.');
                });
        };
        
        this.ws.onmessage = async (event) => {
            if (event.data instanceof ArrayBuffer) {
                // Binary data = audio from Gemini
                await this.playAudioChunk(event.data);
            } else {
                // Text data = control messages
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('Connection Error', 'text-red-500');
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket closed');
            this.updateConnectionStatus('Disconnected', 'text-red-500');
            this.stopRecording();
        };
    }
    
    handleMessage(data) {
        console.log('Received message:', data);
        
        switch (data.type) {
            case 'ready':
                this.updateStatus(data.message);
                this.enableControls();
                break;
            
            case 'progress':
                this.updateProgress(data);
                break;
            
            case 'completed':
                this.handleCompletion(data);
                break;
            
            case 'transcript':
                // AI text for display
                this.addToConversation('AI', data.text);
                break;
            
            case 'error':
                this.showError(data.message);
                break;
        }
    }
    
    async toggleRecording() {
        console.log('Toggle recording - currently:', this.isRecording);
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }
    
    async startRecording() {
        try {
            console.log('Starting recording...');
            console.log('Audio context state:', this.audioContext.state);
            
            // Resume audio context if suspended
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
                console.log('Audio context resumed');
            }
            
            // Get microphone access
            console.log('Requesting microphone access...');
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: this.SEND_SAMPLE_RATE,
                    channelCount: this.CHANNELS,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            console.log('Microphone access granted, creating audio pipeline...');
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);
            
            // Create ScriptProcessor for audio capture
            const bufferSize = 4096;
            const processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
            
            let frameCount = 0;
            processor.onaudioprocess = (e) => {
                if (!this.isRecording) return;
                
                frameCount++;
                
                const inputData = e.inputBuffer.getChannelData(0);
                
                // Check audio level (loudness)
                let sum = 0;
                for (let i = 0; i < inputData.length; i++) {
                    sum += Math.abs(inputData[i]);
                }
                const average = sum / inputData.length;
                
                if (frameCount % 10 === 0) {
                    console.log(`Audio frame ${frameCount} - Level: ${(average * 100).toFixed(2)}%`);
                    if (average < 0.001) {
                        console.warn('⚠️ Audio level very low! Speak louder or check microphone!');
                    }
                }
                
                // Convert Float32 to Int16 PCM
                const pcmData = this.float32ToInt16(inputData);
                
                // Send to WebSocket
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(pcmData.buffer);
                } else {
                    console.warn('WebSocket not open, cannot send audio');
                }
            };
            
            source.connect(processor);
            processor.connect(this.audioContext.destination);
            
            this.audioWorkletNode = processor;
            this.isRecording = true;
            
            console.log('Recording started! Speak now...');
            
            // Update UI
            this.micButton.classList.add('recording', 'bg-red-600');
            this.updateStatus('🔴 RECORDING - Speak now!');
            
        } catch (error) {
            console.error('Error starting recording:', error);
            this.showError('Microphone access denied. Please allow microphone access.');
        }
    }
    
    stopRecording() {
        this.isRecording = false;
        
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        
        if (this.audioWorkletNode) {
            this.audioWorkletNode.disconnect();
            this.audioWorkletNode = null;
        }
        
        // Stop speech recognition
        if (this.recognition) {
            try {
                this.recognition.stop();
                console.log('Speech recognition stopped');
            } catch (e) {
                console.log('Error stopping speech recognition:', e);
            }
        }
        
        // Update UI
        this.micButton.classList.remove('recording', 'bg-red-600');
        this.updateStatus('Click microphone to speak');
    }
    
    async playAudioChunk(arrayBuffer) {
        try {
            // Add to queue instead of playing immediately
            this.audioQueue.push(arrayBuffer);
            
            // Start queue processing if not already running
            if (!this.isPlayingQueue) {
                this.processAudioQueue();
            }
            
        } catch (error) {
            console.error('Error queuing audio:', error);
        }
    }
    
    async processAudioQueue() {
        if (this.isPlayingQueue) return;
        this.isPlayingQueue = true;
        
        console.log('Starting audio queue processing');
        
        while (this.audioQueue.length > 0) {
            const arrayBuffer = this.audioQueue.shift();
            
            try {
                console.log(`Playing ${arrayBuffer.byteLength} bytes from queue (${this.audioQueue.length} remaining)`);
                
                // Convert Int16 PCM to Float32
                const pcmData = new Int16Array(arrayBuffer);
                const floatData = this.int16ToFloat32(pcmData);
                
                // Create audio buffer at 24kHz
                const audioBuffer = this.audioContext.createBuffer(
                    this.CHANNELS,
                    floatData.length,
                    this.RECEIVE_SAMPLE_RATE
                );
                
                audioBuffer.getChannelData(0).set(floatData);
                
                // Play audio and wait for it to finish
                await new Promise((resolve) => {
                    const source = this.audioContext.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(this.audioContext.destination);
                    source.onended = resolve;
                    source.start();
                });
                
            } catch (error) {
                console.error('Error playing audio chunk:', error);
            }
        }
        
        this.isPlayingQueue = false;
        console.log('Audio queue finished');
    }
    
    // Audio conversion utilities
    float32ToInt16(float32Array) {
        const int16Array = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const s = Math.max(-1, Math.min(1, float32Array[i]));
            int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return int16Array;
    }
    
    int16ToFloat32(int16Array) {
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
            float32Array[i] = int16Array[i] / (int16Array[i] < 0 ? 0x8000 : 0x7FFF);
        }
        return float32Array;
    }
    
    // UI Methods
    updateStatus(text) {
        this.statusText.textContent = text;
    }
    
    updateConnectionStatus(text, colorClass) {
        this.connectionStatus.textContent = text;
        this.connectionStatus.className = `text-sm mt-2 ${colorClass}`;
    }
    
    updateProgress(data) {
        const percentage = data.percentage || 0;
        this.progressBar.style.width = `${percentage}%`;
        this.progressText.textContent = `${data.current_field} of ${data.total_fields} fields completed`;
    }
    
    addToConversation(role, message) {
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
        this.stopRecording();
        
        document.getElementById('completion-modal').classList.remove('hidden');
        document.getElementById('completion-message').textContent = data.message;
        
        this.progressBar.style.width = '100%';
        this.addToConversation('System', 'Form completed successfully! 🎉');

        // Display summary as a single paragraph if provided
        if (data.summary && typeof data.summary === 'string') {
            const summaryDiv = document.createElement('div');
            summaryDiv.className = 'p-4 rounded-lg bg-green-50 mt-2';
            const title = document.createElement('div');
            title.className = 'font-semibold text-sm text-green-800 mb-1';
            title.textContent = 'Summary';
            summaryDiv.appendChild(title);
            const p = document.createElement('p');
            p.className = 'text-sm text-green-900';
            p.textContent = data.summary;
            summaryDiv.appendChild(p);
            this.conversationHistory.appendChild(summaryDiv);
            this.conversationHistory.scrollTop = this.conversationHistory.scrollHeight;
        }

        // Display extracted fields if provided
        if (data.extracted_fields && Object.keys(data.extracted_fields).length) {
            const panel = document.createElement('div');
            panel.className = 'p-4 rounded-lg bg-blue-50 mt-2';
            const title = document.createElement('div');
            title.className = 'font-semibold text-sm text-blue-800 mb-1';
            title.textContent = `Extracted Fields${typeof data.confidence === 'number' ? ` (confidence ${data.confidence}%)` : ''}`;
            panel.appendChild(title);
            const list = document.createElement('ul');
            list.className = 'list-disc list-inside text-sm text-blue-900 space-y-0.5';
            Object.entries(data.extracted_fields).forEach(([k, v]) => {
                const li = document.createElement('li');
                li.textContent = `${k}: ${v == null ? '—' : v}`;
                list.appendChild(li);
            });
            panel.appendChild(list);
            this.conversationHistory.appendChild(panel);
            this.conversationHistory.scrollTop = this.conversationHistory.scrollHeight;
        }

        // Show manual finalize overlay to confirm/edit values
        try {
            const overlay = document.getElementById('finalize-overlay');
            const fieldsDiv = document.getElementById('finalize-fields');
            const btn = document.getElementById('btn-save-summary');
            if (overlay && fieldsDiv && btn && Array.isArray(window.formFields)) {
                overlay.classList.remove('hidden');
                fieldsDiv.innerHTML = '';
                window.formFields.forEach(f => {
                    const row = document.createElement('div');
                    row.className = 'grid grid-cols-3 gap-2';
                    const label = document.createElement('label');
                    label.className = 'col-span-1 text-sm text-gray-700';
                    label.textContent = f.name;
                    const input = document.createElement('input');
                    input.className = 'col-span-2 border rounded px-2 py-1';
                    const existing = data.extracted_fields ? data.extracted_fields[f.name] : undefined;
                    if (existing != null) input.value = existing;
                    input.dataset.fieldName = f.name;
                    row.appendChild(label);
                    row.appendChild(input);
                    fieldsDiv.appendChild(row);
                });

                btn.onclick = async () => {
                    const payload = {};
                    Array.from(fieldsDiv.querySelectorAll('input')).forEach(inp => {
                        let val = inp.value;
                        const fname = inp.dataset.fieldName;
                        const def = window.formFields.find(ff => ff.name === fname);
                        if (def && def.type === 'number') {
                            const num = Number(val);
                            if (!Number.isNaN(num)) val = num;
                        }
                        payload[fname] = val || null;
                    });
                    // POST to finalize endpoint
                    try {
                        const res = await fetch(window.finalizeUrl, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ fields: payload })
                        });
                        if (!res.ok) throw new Error(await res.text());
                        overlay.classList.add('hidden');
                        this.addToConversation('System', 'Summary saved. ✅');
                    } catch (e) {
                        console.error(e);
                        this.addToConversation('System', 'Failed to save summary.');
                    }
                };
            }
        } catch (e) {
            console.warn('Finalize overlay error:', e);
        }
    }
    
    showError(message) {
        this.updateStatus(`Error: ${message}`);
        console.error(message);
    }
    
    enableControls() {
        this.micButton.disabled = false;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new LiveAudioInterface(sessionId, wsScheme, wsHost);
    // Wire Close button to gracefully shutdown and fallback-redirect
    const btnClose = document.getElementById('btn-close');
    if (btnClose) {
        btnClose.addEventListener('click', () => {
            try { app.stopRecording(); } catch (e) {}
            try { if (app.ws) app.ws.close(); } catch (e) {}
            // Attempt to close window (may be blocked if not opened by script)
            try { window.close(); } catch (e) {}
            // Fallback: redirect to session completed page if available or home
            setTimeout(() => {
                if (!document.hidden) {
                    const to = `/s/${sessionId}/`;
                    window.location.href = to;
                }
            }, 100);
        });
    }
});

