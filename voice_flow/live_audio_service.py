"""
Gemini Live API Integration for Native Audio Processing
Uses Gemini 2.5 Flash Native Audio with bidirectional streaming
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from google import genai

logger = logging.getLogger(__name__)

# Audio configuration matching Gemini Live API requirements
FORMAT_PYAUDIO = None  # Will be set if pyaudio available
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# Try to import pyaudio
try:
    import pyaudio
    FORMAT_PYAUDIO = pyaudio.paInt16
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning("PyAudio not available. Native audio streaming disabled.")


class GeminiLiveAudioService:
    """
    Service for real-time voice conversation using Gemini Live API
    
    Features:
    - Native audio streaming (no transcription needed)
    - Bidirectional communication
    - Interruption support
    - Low latency
    """
    
    def __init__(self):
        self.api_key = settings.VOICE_FORM_SETTINGS.get('GEMINI_API_KEY')
        self.model = settings.VOICE_FORM_SETTINGS.get(
            'GEMINI_AUDIO_MODEL',
            'gemini-2.5-flash-native-audio-preview-09-2025'
        )
        
        if self.api_key:
            self.client = genai.Client(
                api_key=self.api_key,
                http_options={"api_version": "v1alpha"}
            )
        else:
            self.client = None
            logger.warning("GEMINI_API_KEY not configured")
    
    def create_system_instruction(self, form_config: Dict, current_field: Optional[Dict] = None) -> str:
        """
        Create system instruction for Gemini based on form context
        
        Args:
            form_config: Form configuration with name, description, fields
            current_field: Current field being processed
            
        Returns:
            System instruction string
        """
        instruction_parts = [
            "You are a friendly and helpful AI assistant conducting a voice form interview.",
            f"\nForm Purpose: {form_config.get('description', form_config.get('name'))}",
            f"\nInitial Greeting: {form_config.get('ai_prompt', 'Hello! Let me help you fill out this form.')}",
            "\nYour Role:",
            "- Ask questions one at a time clearly and naturally",
            "- Listen carefully to user responses",
            "- Provide gentle guidance if responses are unclear",
            "- Be encouraging and patient",
            "- Keep the conversation flowing naturally",
            "- Confirm understanding before moving to next question",
        ]
        
        if current_field:
            instruction_parts.extend([
                f"\n\nCurrent Question: {current_field['prompt']}",
                f"Field Type: {current_field['type']}",
                f"Required: {'Yes' if current_field.get('required') else 'No'}",
            ])
            
            # Add validation context
            validation = current_field.get('validation', {})
            if validation:
                instruction_parts.append("\nValidation Requirements:")
                if 'options' in validation:
                    instruction_parts.append(f"- Valid options: {', '.join(validation['options'])}")
                if 'min' in validation:
                    instruction_parts.append(f"- Minimum value: {validation['min']}")
                if 'max' in validation:
                    instruction_parts.append(f"- Maximum value: {validation['max']}")
        
        return "\n".join(instruction_parts)
    
    def create_config(self, system_instruction: str) -> Dict[str, Any]:
        """
        Create configuration for Live API session
        
        Args:
            system_instruction: System instruction for the model
            
        Returns:
            Configuration dictionary
        """
        return {
            "system_instruction": system_instruction,
            "response_modalities": ["AUDIO"],  # Audio-only responses
            "proactivity": {'proactive_audio': True}  # Allow model to be proactive
        }
    
    async def create_session(self, form_config: Dict, current_field: Optional[Dict] = None):
        """
        Create a Live API session
        
        Args:
            form_config: Form configuration
            current_field: Current field being processed
            
        Returns:
            Live session context manager
        """
        if not self.client:
            raise ValueError("Gemini client not initialized. Check GEMINI_API_KEY.")
        
        system_instruction = self.create_system_instruction(form_config, current_field)
        config = self.create_config(system_instruction)
        
        return self.client.aio.live.connect(model=self.model, config=config)
    
    async def send_audio(self, session, audio_data: bytes, mime_type: str = "audio/pcm"):
        """
        Send audio data to Gemini
        
        Args:
            session: Active Live API session
            audio_data: Raw audio bytes (PCM format)
            mime_type: Audio MIME type
        """
        await session.send_realtime_input(audio={"data": audio_data, "mime_type": mime_type})
    
    async def send_text(self, session, text: str):
        """
        Send text input to Gemini (for fallback or testing)
        
        Args:
            session: Active Live API session
            text: Text message
        """
        await session.send_realtime_input(text=text)
    
    async def receive_responses(self, session, audio_callback=None, text_callback=None):
        """
        Receive responses from Gemini
        
        Args:
            session: Active Live API session
            audio_callback: Async callback for audio data
            text_callback: Async callback for text data
        """
        try:
            turn = session.receive()
            async for response in turn:
                if data := response.data:
                    # Audio data received
                    if audio_callback:
                        await audio_callback(data)
                
                if text := response.text:
                    # Text response received (for debugging/transcription)
                    if text_callback:
                        await text_callback(text)
                    logger.debug(f"Gemini text: {text}")
        
        except Exception as e:
            logger.error(f"Error receiving Gemini responses: {e}")
            raise
    
    def validate_audio_format(self, audio_data: bytes, sample_rate: int) -> bool:
        """
        Validate audio data format
        
        Args:
            audio_data: Raw audio bytes
            sample_rate: Sample rate (should be 16000 for sending)
            
        Returns:
            True if valid
        """
        if not audio_data:
            return False
        
        if sample_rate != SEND_SAMPLE_RATE:
            logger.warning(f"Sample rate {sample_rate} != {SEND_SAMPLE_RATE}")
            return False
        
        return True
    
    async def extract_field_value(
        self,
        session,
        field_def: Dict,
        conversation_context: list
    ) -> Dict[str, Any]:
        """
        Extract structured field value from conversation
        
        This sends a follow-up request to extract and validate the field value
        
        Args:
            session: Active Live API session
            field_def: Field definition
            conversation_context: Recent conversation history
            
        Returns:
            Dict with value, is_valid, and validation message
        """
        # Send a structured request to extract the value
        extraction_prompt = f"""
        Based on our conversation, please provide the following information in JSON format:
        
        {{
            "value": <the extracted value for field '{field_def['name']}' or null>,
            "is_valid": <true or false>,
            "message": "<brief confirmation or clarification request>"
        }}
        
        Field type: {field_def['type']}
        Field validation: {field_def.get('validation', {})}
        """
        
        await self.send_text(session, extraction_prompt)
        
        # Receive response
        result = {
            'value': None,
            'is_valid': False,
            'message': 'Please provide your answer.'
        }
        
        try:
            turn = session.receive()
            async for response in turn:
                if text := response.text:
                    # Parse JSON response
                    import json
                    try:
                        parsed = json.loads(text)
                        result.update(parsed)
                    except json.JSONDecodeError:
                        # If not JSON, treat as message
                        result['message'] = text
        
        except Exception as e:
            logger.error(f"Error extracting field value: {e}")
        
        return result


class AudioStreamManager:
    """
    Manages audio streaming for WebSocket connections
    
    Handles:
    - Audio input queue (from user)
    - Audio output queue (to user)
    - Gemini Live API session
    - Bidirectional audio flow
    """
    
    def __init__(self, session_id: str, form_config: Dict):
        self.session_id = session_id
        self.form_config = form_config
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue(maxsize=5)
        self.gemini_service = GeminiLiveAudioService()
        self.session = None
        self.tasks = []
    
    async def start(self, current_field: Optional[Dict] = None):
        """Start audio streaming with Gemini"""
        self.session = await self.gemini_service.create_session(
            self.form_config,
            current_field
        )
        await self.session.__aenter__()
    
    async def stop(self):
        """Stop audio streaming"""
        for task in self.tasks:
            task.cancel()
        
        if self.session:
            await self.session.__aexit__(None, None, None)
    
    async def send_audio_to_gemini(self):
        """Background task to send audio from queue to Gemini"""
        while True:
            audio_data = await self.audio_out_queue.get()
            await self.gemini_service.send_audio(
                self.session,
                audio_data['data'],
                audio_data.get('mime_type', 'audio/pcm')
            )
    
    async def receive_audio_from_gemini(self, websocket_send_callback):
        """Background task to receive audio from Gemini and send to WebSocket"""
        
        async def audio_callback(audio_data):
            # Send audio to client via WebSocket
            await websocket_send_callback({
                'type': 'audio',
                'data': audio_data,
                'format': 'pcm',
                'sample_rate': RECEIVE_SAMPLE_RATE
            })
        
        async def text_callback(text):
            # Send text for display/debugging
            await websocket_send_callback({
                'type': 'transcript',
                'text': text
            })
        
        await self.gemini_service.receive_responses(
            self.session,
            audio_callback=audio_callback,
            text_callback=text_callback
        )
    
    async def queue_audio(self, audio_data: bytes, mime_type: str = "audio/pcm"):
        """Queue audio data to send to Gemini"""
        await self.audio_out_queue.put({
            'data': audio_data,
            'mime_type': mime_type
        })


# Singleton instance
live_audio_service = GeminiLiveAudioService()

