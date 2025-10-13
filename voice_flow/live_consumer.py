"""
WebSocket consumer for Gemini Live API bidirectional audio streaming
Follows Google's reference implementation exactly
"""
import asyncio
import json
import logging
import sys
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from .models import MagicLinkSession
from .tasks import send_webhook

logger = logging.getLogger(__name__)

# For Python < 3.11 compatibility
if sys.version_info < (3, 11, 0):
    try:
        import taskgroup, exceptiongroup
        asyncio.TaskGroup = taskgroup.TaskGroup
        asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup
    except ImportError:
        logger.warning("taskgroup/exceptiongroup not available for Python < 3.11")

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.error("google-genai not installed")


class LiveAudioConsumer(AsyncWebsocketConsumer):
    """
    Gemini 2.5 Flash Live API WebSocket Consumer
    
    Follows the exact pattern from Google's reference code:
    - async with for session and TaskGroup
    - Separate queues for input/output audio
    - Background tasks for send/receive
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.audio_in_queue = None  # Audio from Gemini to client
        self.audio_out_queue = None  # Audio from client to Gemini
        self.gemini_session = None
        self.form_config = None
        self.main_task = None
        
        # Accept WebSocket connection
        await self.accept()
        
        if not GENAI_AVAILABLE:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'google-genai not installed'
            }))
            return
        
        # Get session data
        try:
            session_data = await self.get_session_data()
            if not session_data['is_valid']:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': session_data.get('error', 'Invalid session')
                }))
                return
            
            self.form_config = session_data
            
            # Start the Live API loop (this will run continuously)
            self.main_task = asyncio.create_task(self.run_live_api())
            
            logger.info(f"Live API session started for {self.session_id}")
            
        except Exception as e:
            logger.error(f"Connection error: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def disconnect(self, close_code):
        """Handle disconnection"""
        logger.info(f"Disconnecting session {self.session_id}")
        if self.main_task:
            self.main_task.cancel()
    
    async def receive(self, text_data=None, bytes_data=None):
        """Receive from browser"""
        try:
            if bytes_data and self.audio_out_queue:
                # Audio from browser - send to Gemini
                logger.debug(f"Received {len(bytes_data)} bytes from browser")
                await self.audio_out_queue.put({
                    "data": bytes_data,
                    "mime_type": "audio/pcm"
                })
            elif text_data:
                # Control message
                data = json.loads(text_data)
                logger.debug(f"Control message: {data.get('type')}")
                if data.get('type') == 'start':
                    logger.info("Client ready to start conversation")
        except Exception as e:
            logger.error(f"Receive error: {e}", exc_info=True)
    
    async def run_live_api(self):
        """
        Main Live API loop - follows Google's reference pattern exactly
        This runs continuously with async with and TaskGroup
        """
        try:
            api_key = settings.VOICE_FORM_SETTINGS.get('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set")
            
            # Create Gemini client
            client = genai.Client(
                api_key=api_key,
                http_options={"api_version": "v1alpha"}
            )
            
            # Build system instruction
            system_instruction = self.build_system_instruction()
            
            # Config
            config = {
                "system_instruction": system_instruction,
                "response_modalities": ["AUDIO"],
                "proactivity": {'proactive_audio': True}
            }
            
            model = "gemini-2.5-flash-native-audio-preview-09-2025"
            
            logger.info(f"Connecting to {model}")
            
            # This is the EXACT pattern from Google's reference code
            async with (
                client.aio.live.connect(model=model, config=config) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.gemini_session = session
                
                # Initialize queues
                self.audio_in_queue = asyncio.Queue()  # Gemini → Browser
                self.audio_out_queue = asyncio.Queue(maxsize=5)  # Browser → Gemini
                
                logger.info("Live API connected!")
                
                # Send ready message to browser
                await self.send(text_data=json.dumps({
                    'type': 'ready',
                    'message': 'Live API connected. Click microphone to start!',
                    'form_name': self.form_config['form_name'],
                    'total_fields': self.form_config['total_fields']
                }))
                
                # Start all tasks (pattern from reference code)
                tg.create_task(self.send_realtime())
                tg.create_task(self.receive_audio_from_gemini())
                tg.create_task(self.send_audio_to_browser())
                
                logger.info("All audio tasks started - streaming active!")
                
        except asyncio.CancelledError:
            logger.info("Live API loop cancelled")
        except Exception as e:
            logger.error(f"Live API error: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Live API error: {str(e)}"
            }))
    
    async def send_realtime(self):
        """Send audio from browser to Gemini (from reference code)"""
        logger.info("Ready to send audio to Gemini...")
        try:
            while True:
                msg = await self.audio_out_queue.get()
                logger.debug(f"Sending audio to Gemini: {len(msg['data'])} bytes")
                await self.gemini_session.send_realtime_input(audio=msg)
        except Exception as e:
            logger.error(f"Error sending to Gemini: {e}", exc_info=True)
    
    async def receive_audio_from_gemini(self):
        """Receive audio from Gemini (from reference code)"""
        logger.info("Starting to receive audio from Gemini...")
        try:
            while True:
                turn = self.gemini_session.receive()
                async for response in turn:
                    if data := response.data:
                        # Put audio in queue to send to browser
                        logger.debug(f"Received {len(data)} bytes of audio from Gemini")
                        self.audio_in_queue.put_nowait(data)
                        continue
                    if text := response.text:
                        # Log and send transcript
                        logger.info(f"Gemini says: {text}")
                        await self.send(text_data=json.dumps({
                            'type': 'transcript',
                            'text': text
                        }))
                
                logger.debug("Turn complete")
                
                # Handle interruptions - clear queue (from reference code)
                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
        except Exception as e:
            logger.error(f"Error receiving from Gemini: {e}", exc_info=True)
    
    async def send_audio_to_browser(self):
        """Send audio from queue to browser"""
        logger.info("Ready to send audio to browser...")
        try:
            while True:
                audio_data = await self.audio_in_queue.get()
                logger.debug(f"Sending {len(audio_data)} bytes to browser")
                # Send as binary WebSocket message
                await self.send(bytes_data=audio_data)
        except Exception as e:
            logger.error(f"Error sending to browser: {e}", exc_info=True)
    
    def build_system_instruction(self):
        """Build system instruction for form"""
        fields = self.form_config['fields']
        field_list = []
        
        for i, field in enumerate(fields, 1):
            req = "REQUIRED" if field.get('required') else "optional"
            field_list.append(
                f"{i}. {field['name']} ({field['type']}, {req}): {field['prompt']}"
            )
        
        return f"""
You are conducting a voice form interview for: {self.form_config['form_name']}

{self.form_config.get('ai_prompt', 'Hello! Let me ask you some questions.')}

You need to collect the following information by asking questions ONE AT A TIME:

{chr(10).join(field_list)}

CRITICAL INSTRUCTIONS:
1. IMMEDIATELY greet the user and ask question 1 - don't wait for them to speak first!
2. Ask questions in order, ONE question at a time
3. WAIT for the user's complete response before asking the next question
4. Be friendly, warm, and conversational
5. If a response is unclear, politely ask for clarification
6. Briefly confirm each answer before moving to the next question
7. After ALL questions are answered, say "That completes our survey! Thank you!"
8. Keep responses brief and natural

START NOW by greeting the user and asking question 1!
"""
    
    @database_sync_to_async
    def get_session_data(self):
        """Get session data from database"""
        try:
            session = MagicLinkSession.objects.select_related('form_config').get(
                session_id=self.session_id
            )
            
            if session.is_expired():
                return {'is_valid': False, 'error': 'Session expired'}
            
            if session.status == 'completed':
                return {'is_valid': False, 'error': 'Already completed'}
            
            form = session.form_config
            
            return {
                'is_valid': True,
                'session_id': session.session_id,
                'form_id': form.form_id,
                'form_name': form.name,
                'form_description': form.description,
                'ai_prompt': form.ai_prompt,
                'fields': form.fields,
                'total_fields': len(form.fields),
                'success_message': form.success_message
            }
        except MagicLinkSession.DoesNotExist:
            return {'is_valid': False, 'error': 'Session not found'}
