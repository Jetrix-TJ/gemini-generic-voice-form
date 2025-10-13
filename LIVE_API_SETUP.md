# 🎙️ Gemini Live API Setup Guide

## Using Gemini 2.5 Flash Native Audio with Live API

VoiceGen now supports Google's **Gemini 2.5 Flash Native Audio** model with the **Live API** for true real-time bidirectional audio streaming!

## What is the Live API?

The Live API provides:
- ✅ **Real-time bidirectional audio streaming** - No transcription needed!
- ✅ **Native audio processing** - Gemini understands audio directly
- ✅ **Interruption support** - Users can interrupt the AI naturally
- ✅ **Low latency** - Near-instant responses
- ✅ **Proactive responses** - AI can initiate follow-ups
- ✅ **No chunking needed** - Continuous audio stream

## Model

**Gemini 2.5 Flash Native Audio Preview**
- Model ID: `gemini-2.5-flash-native-audio-preview-09-2025`
- API Version: `v1alpha`
- Features: Real-time audio I/O, interruption, proactivity

## Setup Instructions

### 1. Install Additional Dependencies

The Live API requires `pyaudio` for audio handling:

#### macOS:
```bash
brew install portaudio
pip install pyaudio
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

#### Windows:
```bash
# Download wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
pip install PyAudio‑0.2.14‑cp311‑cp311‑win_amd64.whl
```

### 2. Install Google GenAI SDK

```bash
pip install -U google-genai
```

### 3. Configure Environment

Add to your `.env` file:

```env
# Required: Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Model Configuration (optional - has good defaults)
GEMINI_AUDIO_MODEL=gemini-2.5-flash-native-audio-preview-09-2025
USE_LIVE_API=True
NATIVE_AUDIO_PROCESSING=True
```

### 4. Verify Setup

Test the Live API connection:

```bash
python examples/test_live_api.py
```

## Audio Configuration

The Live API uses specific audio formats:

### Input Audio (User → Gemini)
- **Format:** PCM (16-bit signed integer)
- **Sample Rate:** 16,000 Hz
- **Channels:** Mono (1 channel)
- **Chunk Size:** 1024 samples

### Output Audio (Gemini → User)
- **Format:** PCM (16-bit signed integer)
- **Sample Rate:** 24,000 Hz
- **Channels:** Mono (1 channel)

## How It Works

### Traditional Flow (Old):
```
User speaks → Browser transcribes → Send text → Gemini processes → 
Response text → Browser synthesizes → User hears
```
**Latency:** ~2-5 seconds

### Live API Flow (New):
```
User speaks → Send audio stream → Gemini processes audio → 
Audio response stream → User hears
```
**Latency:** ~300-800ms 🚀

## Features

### 1. Bidirectional Streaming

Both audio input and output stream simultaneously:

```python
from voice_flow.live_audio_service import GeminiLiveAudioService

service = GeminiLiveAudioService()

# Create session
async with await service.create_session(form_config) as session:
    # Send audio
    await service.send_audio(session, audio_chunk, "audio/pcm")
    
    # Receive audio
    async for response in service.receive_responses(session):
        if response.data:
            # Play audio response
            play_audio(response.data)
```

### 2. Interruption Support

Users can interrupt the AI naturally:

```python
# When user starts speaking, stop current playback
while not audio_in_queue.empty():
    audio_in_queue.get_nowait()
```

The Live API automatically detects turn completion and handles interruptions.

### 3. Proactive Responses

Enable the AI to ask follow-up questions:

```python
config = {
    "response_modalities": ["AUDIO"],
    "proactivity": {'proactive_audio': True}  # AI can be proactive
}
```

### 4. System Instructions

Customize AI behavior per form:

```python
system_instruction = """
You are a friendly AI assistant conducting a customer feedback survey.
Be warm, encouraging, and patient. Ask one question at a time.
"""

config = {
    "system_instruction": system_instruction,
    "response_modalities": ["AUDIO"],
    "proactivity": {'proactive_audio': True}
}
```

## WebSocket Integration

The Live API integrates with your WebSocket consumers:

```python
from voice_flow.live_audio_service import AudioStreamManager

class VoiceConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Create audio stream manager
        self.audio_manager = AudioStreamManager(
            session_id=self.session_id,
            form_config=form_config
        )
        
        # Start Live API session
        await self.audio_manager.start(current_field)
    
    async def receive(self, bytes_data=None):
        # Forward audio to Gemini
        if bytes_data:
            await self.audio_manager.queue_audio(bytes_data)
```

## Best Practices

### 1. Use Headphones
**Important:** Use headphones during testing to prevent echo/feedback loops. The AI will hear itself without echo cancellation.

### 2. Optimize Chunk Size
```python
CHUNK_SIZE = 1024  # Good balance of latency vs bandwidth
```

### 3. Handle Errors Gracefully
```python
try:
    async with await service.create_session(config) as session:
        # ... streaming logic
except Exception as e:
    logger.error(f"Live API error: {e}")
    # Fallback to text-based interaction
```

### 4. Monitor Network
Live API requires stable network connection for streaming. Consider:
- Connection recovery logic
- Buffering strategies
- Fallback to text mode

## Troubleshooting

### PyAudio Installation Issues

**macOS:**
```bash
# If brew install fails
xcode-select --install
brew reinstall portaudio
pip install --global-option='build_ext' --global-option='-I/opt/homebrew/include' --global-option='-L/opt/homebrew/lib' pyaudio
```

**Linux:**
```bash
sudo apt-get install build-essential portaudio19-dev
pip install pyaudio
```

**Windows:**
Use pre-built wheels from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

### Audio Not Streaming

1. **Check microphone permissions** - Browser needs mic access
2. **Verify audio format** - Must be PCM 16kHz mono
3. **Check network** - Stable connection required
4. **Review logs** - Check console for errors

### High Latency

1. **Reduce chunk size** - Try 512 or 256 samples
2. **Check network** - Test connection speed
3. **Optimize audio** - Use PCM format
4. **Review system load** - Close other applications

### Interruptions Not Working

1. **Clear audio queue** - Empty queue on interruption
2. **Check turn completion** - Wait for turn_complete
3. **Review buffering** - Don't over-buffer audio

## Performance Comparison

| Metric | Traditional (Web Speech) | Live API |
|--------|-------------------------|----------|
| Latency | 2-5 seconds | 300-800ms |
| Audio Quality | Good | Excellent |
| Interruptions | Limited | Native |
| Context Understanding | Text only | Audio + context |
| Setup Complexity | Simple | Moderate |
| Dependencies | None | PyAudio |

## Example: Complete Live Audio Form

```python
import asyncio
from voice_flow.live_audio_service import GeminiLiveAudioService

async def voice_form_session():
    service = GeminiLiveAudioService()
    
    form_config = {
        'name': 'Customer Feedback',
        'description': 'Quick feedback survey',
        'ai_prompt': 'Hello! I have a few quick questions.',
        'fields': [
            {
                'name': 'satisfaction',
                'type': 'number',
                'prompt': 'On a scale of 1-10, how satisfied are you?',
                'validation': {'min': 1, 'max': 10}
            }
        ]
    }
    
    async with await service.create_session(form_config) as session:
        # Audio streaming would happen here
        # In practice, this connects to WebSocket
        pass

asyncio.run(voice_form_session())
```

## API Limits

**Gemini 2.5 Flash Native Audio:**
- Requests per minute: ~60
- Concurrent sessions: ~5
- Audio streaming: Unlimited duration per session
- Rate limiting: Per API key

Check your limits: https://makersuite.google.com/app/apikey

## Migration from Old API

If upgrading from text-based API:

1. **Install dependencies:**
   ```bash
   pip install google-genai pyaudio
   ```

2. **Update .env:**
   ```env
   USE_LIVE_API=True
   GEMINI_AUDIO_MODEL=gemini-2.5-flash-native-audio-preview-09-2025
   ```

3. **No code changes needed** - Auto-detects and uses Live API!

4. **Test thoroughly** - Audio streaming is different from text

## Resources

- **Live API Docs:** https://ai.google.dev/api/live
- **Audio Requirements:** https://ai.google.dev/api/live#audio-requirements
- **Code Examples:** https://github.com/google-gemini/cookbook
- **API Key:** https://makersuite.google.com/app/apikey

## Support

Questions about Live API setup?
- 📧 Email: support@voicegen.ai
- 💬 Discord: https://discord.gg/voicegen
- 📖 Docs: https://docs.voicegen.ai/live-api

---

**Ready to go!** The Live API provides the best voice form experience with near-instant responses and natural interruptions. 🎙️✨

