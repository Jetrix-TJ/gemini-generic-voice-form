import asyncio
import base64
import json
import logging

import google.generativeai as genai
from google import genai as genai_client
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from google.genai import types

from .models import DynamicFormData, MagicLinkSession
from .utils import save_form_field

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


class VoiceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time voice communication with Google Gemini Live API
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gemini_client = None
        self.live_session = None

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"voice_session_{self.session_id}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name, self.channel_name
        )

        await self.accept()

        # Initialize or get existing voice session
        await self.get_magic_link_session()

        logger.info(f"Voice consumer connected for session {self.session_id}")

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name, self.channel_name
        )

        # Close Gemini Live session if active
        if self.live_session:
            try:
                await self.live_session.close()
            except Exception as e:
                logger.error(f"Error closing Live session: {e}")

        logger.info(
            f"Voice consumer disconnected for session {self.session_id}"
        )

    async def receive(self, text_data):
        try:
            logger.info(f"📨 Raw WebSocket data received: {repr(text_data[:200])}...")
            data = json.loads(text_data)
            message_type = data.get("type")
            
            logger.info(f"📨 Received WebSocket message: type={message_type}, data={data}")

            if message_type == "setup":
                await self.handle_setup(data)
            elif message_type == "audio":
                await self.handle_audio(data)
            elif message_type == "text":
                await self.handle_text(data)
            elif message_type == "turn_complete":
                await self.handle_turn_complete(data)
            else:
                logger.warning(f"⚠️ Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON received: {e}")
            logger.error(f"❌ Raw data: {repr(text_data)}")
            await self.send_error("Invalid JSON received")
        except Exception as e:
            logger.error(f"❌ Error in receive: {str(e)}", exc_info=True)
            await self.send_error(f"Server error: {str(e)}")

    async def handle_setup(self, data):
        """Initialize the conversation with Gemini Live API"""
        try:
            logger.info(f"🔧 Setup request received: {data}")
            logger.info(f"🔧 Session ID from URL: {self.session_id}")
            
            # Check if API key is available
            if not settings.GEMINI_API_KEY:
                logger.error("❌ GEMINI_API_KEY not found in settings")
                await self.send_error("Gemini API key not configured")
                return
            
            # Test basic API connectivity first
            try:
                logger.info("🔍 Testing basic Gemini API connectivity...")
                test_client = genai_client.Client(api_key=settings.GEMINI_API_KEY)
                models = test_client.models.list()
                available_models = [model.name for model in models]
                logger.info(f"📋 Available models: {available_models[:5]}...")  # Show first 5 models
            except Exception as e:
                logger.warning(f"⚠️ Could not list models: {str(e)}")
                logger.info("🔄 Continuing with connection attempts...")
            
            # Get the magic link session and form configuration
            session = await self.get_magic_link_session()
            if not session:
                logger.error(f"❌ No session found for session_id: {self.session_id}")
                await self.send_error("Invalid or expired session")
                return

            form_config = session.form_config

            # Initialize Gemini Live API client with correct configuration
            self.gemini_client = genai_client.Client(
                http_options={"api_version": "v1beta"},
                api_key=settings.GEMINI_API_KEY
            )
            
            # Configure Live API session based on official example
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO", "TEXT"],
                system_instruction=self.get_dynamic_system_instruction(form_config),
                media_resolution="MEDIA_RESOLUTION_MEDIUM",
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                    )
                ),
                context_window_compression=types.ContextWindowCompressionConfig(
                    trigger_tokens=25600,
                    sliding_window=types.SlidingWindow(target_tokens=12800),
                ),
            )

            # Start Live API session
            logger.info(f"Starting Gemini Live API session with model: {settings.GEMINI_MODEL}")
            logger.info(f"API Key present: {bool(settings.GEMINI_API_KEY)}")
            logger.info(f"API Key length: {len(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else 0}")
            
            # Try different model names if the current one fails
            models_to_try = [
                settings.GEMINI_MODEL,
                "models/gemini-2.5-flash-native-audio-preview-09-2025",
                "models/gemini-live-2.5-flash-preview",
                "models/gemini-2.0-flash-exp",
                "models/gemini-1.5-flash",
                "models/gemini-1.5-pro"
            ]
            
            connection_successful = False
            for model in models_to_try:
                try:
                    logger.info(f"🔄 Trying model: {model}")
                    self.live_session = await self.gemini_client.aio.live.connect(
                        model=model,
                        config=config
                    ).__aenter__()
                    logger.info(f"✅ Gemini Live API session connected successfully with model: {model}")
                    connection_successful = True
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Model {model} failed: {str(e)}")
                    continue
            
            if not connection_successful:
                logger.error("❌ All Gemini Live API models failed to connect")
                logger.info("🔄 Falling back to regular Gemini API without Live features")
                
                # Fallback to regular Gemini API
                try:
                    # Try different model names for regular API
                    fallback_models = [
                        "gemini-2.0-flash-exp",
                        "gemini-1.5-flash", 
                        "gemini-1.5-pro"
                    ]
                    
                    fallback_successful = False
                    for model in fallback_models:
                        try:
                            logger.info(f"🔄 Trying fallback model: {model}")
                            self.gemini_model = genai.GenerativeModel(model)
                            self.use_live_api = False
                            logger.info(f"✅ Fallback to regular Gemini API successful with model: {model}")
                            fallback_successful = True
                            break
                        except Exception as e:
                            logger.warning(f"⚠️ Fallback model {model} failed: {str(e)}")
                            continue
                    
                    if not fallback_successful:
                        logger.error("❌ All fallback models also failed")
                        await self.send_error("Unable to connect to any Gemini API")
                        return
                        
                except Exception as e:
                    logger.error(f"❌ Fallback setup failed: {str(e)}")
                    await self.send_error("Unable to connect to any Gemini API")
                    return
            else:
                self.use_live_api = True

            # Send welcome message
            api_type = "Live API" if self.use_live_api else "Regular API (text only)"
            await self.send(text_data=json.dumps({
                "type": "setup_complete",
                "session_id": str(session.id),
                "form_name": form_config.name,
                "message": f"Voice assistant ready for {form_config.name} using {api_type}. Please start {'speaking' if self.use_live_api else 'typing'}.",
            }))

            # Start listening for responses only if using Live API
            if self.use_live_api:
                asyncio.create_task(self.listen_to_gemini_responses())

        except Exception as e:
            logger.error(f"Setup error: {str(e)}", exc_info=True)
            await self.send_error(f"Setup failed: {str(e)}")

    async def listen_to_gemini_responses(self):
        """Listen for responses from Gemini Live API"""
        try:
            turn = self.live_session.receive()
            async for response in turn:
                await self.process_gemini_live_response(response)
        except Exception as e:
            logger.error(f"Error listening to Gemini responses: {e}")

    async def handle_audio(self, data):
        """Process audio data from client"""
        try:
            logger.info("🎤 Received audio message from client")
            audio_data = data.get("audio")
            if not audio_data:
                logger.error("❌ No audio data in message")
                await self.send_error("No audio data received")
                return

            logger.info(f"✅ Audio data length: {len(audio_data)} chars (base64)")
            
            if self.use_live_api and self.live_session:
                # Use Live API for real-time audio processing
                audio_bytes = base64.b64decode(audio_data)
                logger.info(f"✅ Decoded audio bytes: {len(audio_bytes)} bytes")
                
                # Send audio in the format expected by the new API
                await self.live_session.send(input={
                    "data": audio_bytes,
                    "mime_type": "audio/pcm"
                })
            else:
                # Fallback: inform user that audio processing is not available
                await self.send(text_data=json.dumps({
                    "type": "gemini_response",
                    "text": "Audio processing is currently not available. Please use text input.",
                    "audio": None,
                    "function_calls": []
                }))

        except Exception as e:
            logger.error(f"❌ Audio processing error: {str(e)}", exc_info=True)
            await self.send_error(f"Audio processing failed: {str(e)}")

    async def handle_text(self, data):
        """Process text message from client"""
        try:
            text = data.get("text", "")
            if not text:
                await self.send_error("No text received")
                return

            if self.use_live_api and self.live_session:
                # Use Live API for real-time text processing
                await self.live_session.send(input=text, end_of_turn=True)
            elif hasattr(self, 'gemini_model'):
                # Use regular Gemini API
                try:
                    response = await self.gemini_model.generate_content_async(text)
                    response_text = response.text if response and response.text else "I'm sorry, I couldn't generate a response."
                    await self.send(text_data=json.dumps({
                        "type": "gemini_response",
                        "text": response_text,
                        "audio": None,
                        "function_calls": []
                    }))
                except Exception as e:
                    logger.error(f"Regular API text processing error: {str(e)}")
                    await self.send_error(f"Text processing failed: {str(e)}")
            else:
                await self.send_error("No Gemini API connection available")

        except Exception as e:
            logger.error(f"Text processing error: {str(e)}")
            await self.send_error(f"Text processing failed: {str(e)}")

    async def handle_turn_complete(self, data):
        """Handle turn completion"""
        try:
            # Get the current session
            session = await self.get_magic_link_session()
            if not session:
                return
            
            # Calculate simple progress based on session data
            form_config = session.form_config
            total_fields = 0
            completed_fields = len(session.session_data)
            
            # Count total fields from form schema
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
            logger.error(f"Turn complete error: {str(e)}")

    async def process_gemini_live_response(self, response):
        """Process response from Gemini Live API"""
        try:
            response_data = {
                "type": "gemini_response",
                "text": "",
                "audio": None,
                "function_calls": []
            }

            # Handle text response
            if hasattr(response, 'text') and response.text:
                response_data["text"] += response.text
                print(response.text, end="")  # Print to console like in the example

            # Handle audio response
            if hasattr(response, 'data') and response.data:
                response_data["audio"] = base64.b64encode(response.data).decode('utf-8')

            # Handle function calls (if any)
            if hasattr(response, 'function_call') and response.function_call:
                function_call = {
                    "name": response.function_call.name,
                    "args": dict(response.function_call.args)
                }
                response_data["function_calls"].append(function_call)
                await self.process_function_call(function_call)

            # Only send response to client if there's actual content
            if response_data["text"] or response_data["audio"] or response_data["function_calls"]:
                await self.send(text_data=json.dumps(response_data))

        except Exception as e:
            logger.error(f"Response processing error: {str(e)}")
            await self.send_error(f"Response processing failed: {str(e)}")



    async def process_function_call(self, call):
        """Process function calls from Gemini"""
        try:
            function_name = call["name"]
            args = call["args"]

            if function_name == "save_form_field":
                await self.save_form_field_async(args)

        except Exception as e:
            logger.error(f"Function call error: {str(e)}")

    async def save_form_field_async(self, args):
        """Save form field asynchronously"""
        try:
            field_name = args.get("field_name")
            field_value = args.get("field_value")
            session_id = args.get("session_id")

            if not all([field_name, field_value, session_id]):
                logger.error("Missing required parameters for save_form_field")
                return

            session = await database_sync_to_async(
                MagicLinkSession.objects.get
            )(id=session_id)

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
            logger.error(f"Save field error: {str(e)}")

    async def send_error(self, message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({"type": "error", "message": message}))

    def get_dynamic_system_instruction(self, form_config):
        """Get dynamic system instruction based on form configuration"""
        # Start with a simple, safe instruction
        base_instructions = """You are a professional voice assistant helping to collect information through natural conversation. Be professional, empathetic, and clear. Ask one question at a time and confirm information before proceeding."""

        # Add form context if available
        if form_config:
            form_context = f"Form: {form_config.name}. {form_config.description or ''}"
            base_instructions = base_instructions + " " + form_context

        # Ensure the instruction is not too long and contains only safe characters
        if len(base_instructions) > 2000:
            base_instructions = base_instructions[:2000]
            
        logger.info(f"📝 System instruction length: {len(base_instructions)} characters")
        return base_instructions

    @database_sync_to_async
    def get_magic_link_session_sync(self):
        """Get magic link session from session ID (sync version)"""
        try:
            from django.utils import timezone
            import uuid

            logger.info(f"🔍 Looking for session with magic_link_id: {self.session_id}")
            
            # Validate UUID format
            try:
                uuid.UUID(self.session_id)
            except ValueError:
                logger.error(f"❌ Invalid UUID format for session_id: {self.session_id}")
                return None

            session = MagicLinkSession.objects.select_related('form_config').get(
                magic_link_id=self.session_id,
                completion_status="active"
            )

            if timezone.now() > session.expires_at:
                logger.warning(f"⚠️ Session expired: {self.session_id}")
                session.completion_status = "expired"
                session.save()
                return None

            logger.info(f"✅ Found session: {session.id}")
            return session
        except MagicLinkSession.DoesNotExist:
            logger.error(f"❌ Magic link session not found: {self.session_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Magic link session retrieval error: {str(e)}")
            return None

    async def get_magic_link_session(self):
        """Get magic link session from session ID"""
        return await self.get_magic_link_session_sync()

    async def update_conversation_history(self, text, function_calls):
        """Update conversation history in magic link session"""
        try:
            session = await self.get_magic_link_session()
            if session:
                history_entry = {
                    "text": text,
                    "function_calls": function_calls,
                    "timestamp": asyncio.get_event_loop().time(),
                }

                session.conversation_history.append(history_entry)
                await database_sync_to_async(session.save)()

        except Exception as e:
            logger.error(f"History update error: {str(e)}")
