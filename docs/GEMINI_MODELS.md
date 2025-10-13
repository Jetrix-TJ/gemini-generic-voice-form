# Gemini Model Configuration

VoiceGen supports Google's latest Gemini models with native audio processing capabilities.

## Available Models

### Gemini 2.0 Flash (Experimental) - **RECOMMENDED**
- **Model ID:** `gemini-2.0-flash-exp`
- **Status:** Latest experimental model
- **Features:**
  - Native audio input support
  - Faster processing
  - Improved conversation quality
  - Best for real-time voice applications
- **Use Case:** Production-ready for voice forms

### Gemini 1.5 Pro
- **Model ID:** `gemini-1.5-pro`
- **Status:** Stable production model
- **Features:**
  - Multimodal support (text, audio, images)
  - Native audio processing
  - Long context window
  - High accuracy
- **Use Case:** When you need stability over speed

### Gemini 1.5 Flash
- **Model ID:** `gemini-1.5-flash`
- **Status:** Stable fast model
- **Features:**
  - Fast processing
  - Audio capabilities
  - Good for high-volume
- **Use Case:** High-traffic applications

## Configuration

### Set Model in Environment

Add to your `.env` file:

```env
# Use Gemini 2.0 Flash (default)
GEMINI_MODEL=gemini-2.0-flash-exp

# Or use Gemini 1.5 Pro for stability
# GEMINI_MODEL=gemini-1.5-pro

# Or use Gemini 1.5 Flash for speed
# GEMINI_MODEL=gemini-1.5-flash
```

### Enable Native Audio Processing

```env
# Enable native audio processing (default: True)
NATIVE_AUDIO_PROCESSING=True

# Disable to use Web Speech API client-side only
# NATIVE_AUDIO_PROCESSING=False
```

## Native Audio vs Transcription

### Native Audio Processing (Recommended)
- **Enabled by default** with Gemini 2.0 Flash
- Audio sent directly to Gemini
- Better understanding of tone, emotion, context
- More natural conversation flow
- Lower latency

### Client-Side Transcription (Fallback)
- Uses Web Speech API in browser
- Converts speech to text first
- Then sends text to Gemini
- Works when native audio isn't available
- Good browser support

## Feature Comparison

| Feature | Gemini 2.0 Flash | Gemini 1.5 Pro | Gemini 1.5 Flash |
|---------|------------------|----------------|------------------|
| Native Audio | ✅ Yes | ✅ Yes | ✅ Yes |
| Speed | ⚡ Very Fast | 🔄 Moderate | ⚡ Fast |
| Accuracy | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Context Window | Large | Very Large | Large |
| Cost | $ | $$ | $ |
| Stability | Experimental | Stable | Stable |

## Supported Audio Formats

All models support these audio formats:
- **WebM** - Browser default (recommended)
- **WAV** - High quality, larger files
- **MP3** - Compressed, good quality
- **OGG** - Open format
- **Opus** - Modern codec

## Usage Examples

### Python SDK

```python
from voiceforms import VoiceFormSDK

# Default uses Gemini 2.0 Flash
sdk = VoiceFormSDK(api_key='your_key')

# Model is configured in .env
# GEMINI_MODEL=gemini-2.0-flash-exp
```

### Direct API Configuration

Edit `voicegen/settings.py`:

```python
VOICE_FORM_SETTINGS = {
    'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY'),
    'GEMINI_MODEL': 'gemini-2.0-flash-exp',  # Change here
    'NATIVE_AUDIO_PROCESSING': True,
    # ... other settings
}
```

## Testing Different Models

```bash
# Test with Gemini 2.0 Flash
GEMINI_MODEL=gemini-2.0-flash-exp python manage.py runserver

# Test with Gemini 1.5 Pro
GEMINI_MODEL=gemini-1.5-pro python manage.py runserver

# Test with Gemini 1.5 Flash
GEMINI_MODEL=gemini-1.5-flash python manage.py runserver
```

## Performance Tips

### For Best Quality
Use **Gemini 1.5 Pro**:
```env
GEMINI_MODEL=gemini-1.5-pro
NATIVE_AUDIO_PROCESSING=True
```

### For Best Speed
Use **Gemini 2.0 Flash**:
```env
GEMINI_MODEL=gemini-2.0-flash-exp
NATIVE_AUDIO_PROCESSING=True
```

### For High Volume
Use **Gemini 1.5 Flash**:
```env
GEMINI_MODEL=gemini-1.5-flash
NATIVE_AUDIO_PROCESSING=True
```

## Troubleshooting

### Model Not Found Error

If you see `Model not found`:
1. Check your model name spelling
2. Verify your API key has access to that model
3. Try using a stable model: `gemini-1.5-pro`

### Audio Processing Fails

If native audio fails:
1. Check `NATIVE_AUDIO_PROCESSING=True` in `.env`
2. Verify audio format is supported
3. Ensure file size < 10MB
4. Falls back to Web Speech API automatically

### Slow Response Times

If responses are slow:
1. Switch to Gemini 2.0 Flash or 1.5 Flash
2. Reduce audio file size
3. Use shorter audio clips
4. Check network connection

## API Limits

Each model has different rate limits:

- **Gemini 2.0 Flash:** ~60 requests/minute
- **Gemini 1.5 Pro:** ~10 requests/minute  
- **Gemini 1.5 Flash:** ~60 requests/minute

Check Google AI Studio for your specific limits:
https://makersuite.google.com/app/apikey

## Future Models

VoiceGen will automatically support new Gemini models as they're released. Simply update the `GEMINI_MODEL` environment variable.

## Getting API Access

1. Visit: https://makersuite.google.com/app/apikey
2. Create or select a project
3. Generate API key
4. Add to `.env` file:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

## Questions?

- 📧 Email: support@voicegen.ai
- 📖 Docs: https://docs.voicegen.ai
- 🐛 Issues: https://github.com/your-org/voicegen/issues

---

**Current Default:** Gemini 2.0 Flash (`gemini-2.0-flash-exp`)  
**Recommended for Production:** Gemini 2.0 Flash or Gemini 1.5 Pro

