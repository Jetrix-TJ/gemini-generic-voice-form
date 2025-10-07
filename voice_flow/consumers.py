import asyncio
import base64
import json
import logging
from typing import Optional, Any

import google.generativeai as genai
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .models import DynamicFormData, MagicLinkSession

logger = logging.getLogger(__name__)


class VoiceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for voice communication with Gemini API
    Falls back gracefully when Live API is not available
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.genai_client = None
        self.genai_model = None
        self.live_session = None
        self.session_active = False
        self.response_listener_task = None
        self.use_live_api = False

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"voice_session_{self.session_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        logger.info(f"Voice consumer connected for session {self.session_id}")

    async def disconnect(self, close_code):
        self.session_active = False
        
        if self.response_listener_task and not self.response_listener_task.done():
            self.response_listener_task.cancel()
            try:
                await self.response_listener_task
            except asyncio.CancelledError:
                pass

        if self.live_session:
            try:
                await self.live_session.close()
                logger.info("Live session closed")
            except Exception as e:
                logger.error(f"Error closing live session: {e}")

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info(f"Voice consumer disconnected for session {self.session_id}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")
            
            logger.info(f"Received message type: {message_type}")

            if message_type == "setup":
                await self.handle_setup(data)
            elif message_type == "audio":
                await self.handle_audio(data)
            elif message_type == "turn_complete":
                await self.handle_turn_complete()
            elif message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            await self.send_error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error in receive: {e}", exc_info=True)
            await self.send_error(f"Server error: {str(e)}")

    async def handle_setup(self, data):
        """Initialize directly with Gemini Live API - skip standard API"""
        try:
            logger.info("Setting up Gemini Live API for voice...")
            
            if not settings.GEMINI_API_KEY:
                await self.send_error("Gemini API key not configured")
                return
            
            session = await self.get_magic_link_session()
            if not session:
                await self.send_error("Invalid or expired session")
                return

            # Go directly to Live API test - this is what you want for voice
            live_api_success = await self.test_live_api()
            
            if live_api_success:
                self.use_live_api = True
                mode = "Live Audio API"
                message = f"Voice assistant ready for {session.form_config.name} with real-time audio"
                
                # Start response listener
                self.response_listener_task = asyncio.create_task(self.listen_to_live_responses())
                
                # Don't send initial greeting during setup to avoid method signature issues
                # Will send greeting when user first speaks
                logger.info("Live API connection established, ready for voice input")
                
            else:
                await self.send_error("Live Audio API not available - this interface requires voice functionality")
                return

            self.session_active = True
            
            # Send success response
            await self.send(text_data=json.dumps({
                "type": "setup_complete",
                "session_id": str(session.id),
                "form_name": session.form_config.name,
                "mode": mode,
                "live_api_available": True,
                "message": message,
            }))
            
            logger.info("Live Audio API setup complete")
            
        except Exception as e:
            logger.error(f"Setup failed: {e}", exc_info=True)
            await self.send_error(f"Voice setup failed: {str(e)}")

    # Remove the standard API test - not needed for voice interface
    # async def test_standard_api(self): - REMOVED

    async def test_live_api(self):
        """Test Live API connection with correct voice configuration"""
        try:
            logger.info("Testing Gemini Live API for voice...")
            
            # Import Live API client
            try:
                from google import genai as genai_client
                logger.info("Live API library available")
            except ImportError as e:
                logger.error(f"Live API library not available: {e}")
                logger.error("Install with: pip install google-genai")
                return False
            
            # Create client
            self.genai_client = genai_client.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("Live API client created")
            
            # Use the WORKING configuration for audio + transcription
            logger.info("Creating Live API config for voice...")
            config = genai_client.types.LiveConnectConfig(
                response_modalities=["AUDIO"],  # Audio only here
                output_audio_transcription=genai_client.types.AudioTranscriptionConfig(),  # This enables text
                speech_config=genai_client.types.SpeechConfig(
                    voice_config=genai_client.types.VoiceConfig(
                        prebuilt_voice_config=genai_client.types.PrebuiltVoiceConfig(
                            voice_name="Puck"  # Use Puck voice
                        )
                    )
                )
            )
            
            # Connect to Live API with the correct model
            logger.info("Connecting to Live API...")
            self.live_session = await self.genai_client.aio.live.connect(
                model="models/gemini-2.0-flash-exp",  # Correct model for Live API
                config=config
            ).__aenter__()
            
            logger.info("Live API connection successful!")
            return True
            
        except Exception as e:
            logger.error(f"Live API test failed: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            if "1007" in str(e):
                logger.error("Live API not available for your account yet (limited preview)")
            return False

    async def listen_to_live_responses(self):
        """Listen for responses from Live API"""
        try:
            logger.info("Starting Live API response listener...")
            
            async for response in self.live_session.receive():
                if not self.session_active:
                    break
                    
                await self.process_live_response(response)
                
        except asyncio.CancelledError:
            logger.info("Live API response listener cancelled")
        except Exception as e:
            logger.error(f"Error in Live API response listener: {e}", exc_info=True)

    async def process_live_response(self, response):
        """Process responses from Live API - Updated for working audio+transcription"""
        try:
            response_data = {
                "type": "gemini_response",
                "text": "",
                "audio": None,
                "function_calls": [],
                "mode": "live_audio"
            }

            if hasattr(response, 'server_content') and response.server_content:
                content = response.server_content
                
                # Handle text transcription (from audio output)
                if hasattr(content, 'output_transcription') and content.output_transcription:
                    response_data["text"] = content.output_transcription.text
                    logger.info(f"Audio transcription: {content.output_transcription.text[:100]}...")
                
                # Handle model turn (contains audio and other content)
                if hasattr(content, 'model_turn') and content.model_turn:
                    for part in content.model_turn.parts:
                        # Handle audio data in parts
                        if hasattr(part, 'audio') and part.audio and hasattr(part.audio, 'data'):
                            response_data["audio"] = base64.b64encode(part.audio.data).decode('utf-8')
                            logger.info(f"Audio response from part: {len(part.audio.data)} bytes")
                        
                        # Handle text content (backup)
                        if hasattr(part, 'text') and part.text:
                            if not response_data["text"]:  # Only use if no transcription
                                response_data["text"] = part.text
                                logger.info(f"Text response: {part.text[:100]}...")
                            
                        # Handle function calls
                        if hasattr(part, 'function_call') and part.function_call:
                            function_call = {
                                "name": part.function_call.name,
                                "args": dict(part.function_call.args)
                            }
                            response_data["function_calls"].append(function_call)
                            await self.process_function_call(function_call)

            # Handle direct audio data (fallback)
            if hasattr(response, 'data') and response.data:
                response_data["audio"] = base64.b64encode(response.data).decode('utf-8')
                logger.info(f"Direct audio response: {len(response.data)} bytes")

            # Send response if there's content
            if response_data["text"] or response_data["audio"] or response_data["function_calls"]:
                await self.send(text_data=json.dumps(response_data))
                logger.info("Live audio+transcription response sent to client")

        except Exception as e:
            logger.error(f"Error processing Live response: {e}", exc_info=True)

    async def handle_audio(self, data):
        """Process audio data from client"""
        try:
            if not self.session_active:
                await self.send_error("Session not active")
                return

            audio_data = data.get("audio")
            if not audio_data:
                await self.send_error("No audio data received")
                return

            if self.use_live_api and self.live_session:
                # Process with Live API
                try:
                    audio_bytes = base64.b64decode(audio_data)
                    logger.info(f"Processing audio via Live API: {len(audio_bytes)} bytes")
                    
                    audio_input = {
                        "data": audio_bytes,
                        "mime_type": "audio/pcm;rate=16000;channels=1"
                    }
                    
                    await self.live_session.send(input=audio_input)
                    logger.info("Audio sent to Live API")
                    
                except Exception as live_error:
                    logger.error(f"Live API audio error: {live_error}")
                    await self.send_error("Audio processing failed")
            else:
                # Standard API fallback - convert audio to text description
                await self.send(text_data=json.dumps({
                    "type": "gemini_response", 
                    "text": "I received your audio message, but Live API is not available. Please describe what you said in text, and I'll help you with your form.",
                    "audio": None,
                    "function_calls": [],
                    "mode": "standard_fallback"
                }))

        except Exception as e:
            logger.error(f"Audio processing error: {e}", exc_info=True)
            await self.send_error(f"Audio processing failed: {str(e)}")

    async def handle_turn_complete(self):
        """Handle end of turn - only send end_of_turn after we confirm method signature"""
        try:
            if self.use_live_api and self.live_session:
                # TODO: Test correct method signature before enabling
                # await self.live_session.send(end_of_turn=True)
                logger.info("Turn complete received (end_of_turn not sent until method signature confirmed)")
            
            await self.update_progress()

        except Exception as e:
            logger.error(f"Turn complete error: {e}")

    async def process_function_call(self, call):
        """Process function calls"""
        try:
            function_name = call["name"]
            args = call["args"]

            if function_name == "save_form_field":
                await self.save_form_field_async(args)

        except Exception as e:
            logger.error(f"Function call error: {e}")

    async def save_form_field_async(self, args):
        """Save form field"""
        try:
            field_name = args.get("field_name")
            field_value = args.get("field_value")
            
            if not field_name or field_value is None:
                return

            session = await self.get_magic_link_session()
            if not session:
                return

            await database_sync_to_async(
                DynamicFormData.objects.update_or_create
            )(
                session=session,
                field_name=field_name,
                defaults={
                    "field_value": str(field_value),
                    "field_type": "voice_input",
                },
            )

            session.session_data[field_name] = field_value
            await database_sync_to_async(session.save)()

            await self.send(text_data=json.dumps({
                "type": "field_saved",
                "field_name": field_name,
                "field_value": field_value,
            }))

        except Exception as e:
            logger.error(f"Save field error: {e}")

    async def update_progress(self):
        """Update progress"""
        try:
            session = await self.get_magic_link_session()
            if not session:
                return
            
            form_config = session.form_config
            completed_fields = len(session.session_data)
            
            total_fields = 0
            if form_config.form_schema and 'sections' in form_config.form_schema:
                for section in form_config.form_schema['sections']:
                    total_fields += len(section.get('fields', []))
            
            progress = (completed_fields / total_fields * 100) if total_fields > 0 else 0
            
            await self.send(text_data=json.dumps({
                "type": "progress_update", 
                "completed": completed_fields,
                "total": total_fields,
                "progress": round(progress)
            }))

        except Exception as e:
            logger.error(f"Progress update error: {e}")

    def get_initial_greeting(self, form_config):
        """Get initial greeting message"""
        if not form_config:
            return "Hello! I'm your assistant. How can I help you today?"
        
        return f"Hello! I'm your assistant for the {form_config.name} form. I'm ready to help you fill it out. What information do you need to provide?"

    async def send_error(self, message):
        """Send error message"""
        await self.send(text_data=json.dumps({
            "type": "error", 
            "message": message
        }))
        logger.error(f"Sent error to client: {message}")

    @database_sync_to_async
    def get_magic_link_session_sync(self):
        """Get session from database"""
        try:
            from django.utils import timezone
            import uuid

            try:
                uuid.UUID(self.session_id)
            except ValueError:
                return None

            session = MagicLinkSession.objects.select_related('form_config').get(
                magic_link_id=self.session_id,
                completion_status="active"
            )

            if timezone.now() > session.expires_at:
                session.completion_status = "expired"
                session.save()
                return None

            return session
            
        except MagicLinkSession.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Session error: {e}")
            return None

    async def get_magic_link_session(self):
        """Get session"""
        return await self.get_magic_link_session_sync()