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
from django.utils import timezone
from .models import MagicLinkSession
from .tasks import send_webhook
from .ai_service import ai_service

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
        self.conversation_history = []  # Track conversation
        self.current_field_index = 0  # Track which field we're on
        self.collected_data = {}  # Store responses
        # Server-side silence detection state
        self._silence_threshold_abs = 120  # average absolute amplitude threshold (16-bit)
        self._silence_timeout_ms = 6500
        self._last_sound_monotonic = None
        self._speech_detected = False
        self._silence_monitor_triggered = False
        # Coordinate completion with model-provided summary
        self._summary_event = asyncio.Event()
        # Additional guards
        self._last_client_audio_monotonic = None
        self._last_ai_audio_monotonic = None
        
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
                # Update silence detector (RMS over 16-bit PCM)
                try:
                    from array import array
                    pcm = array('h')
                    pcm.frombytes(bytes_data)
                    if pcm:
                        avg_abs = sum(1 if v == -32768 else abs(v) for v in pcm) / len(pcm)
                        now = asyncio.get_running_loop().time()
                        if avg_abs >= self._silence_threshold_abs:
                            self._last_sound_monotonic = now
                            self._speech_detected = True
                            # Consider this as active client speech for gap checks
                            self._last_client_audio_monotonic = now
                        elif self._last_sound_monotonic is None:
                            self._last_sound_monotonic = now
                except Exception as e:
                    logger.debug(f"Silence detector error (ignored): {e}")
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
                elif data.get('type') == 'user_transcript':
                    # Track user's speech 
                    user_text = data.get('text', '')
                    self.conversation_history.append({'role': 'user', 'text': user_text})
                elif data.get('type') == 'manual_complete':
                    # Manual completion trigger from UI
                    logger.info("Manual completion triggered by user")
                    await self.handle_completion()
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
            
            # Define tool functions for structured extraction (no transcription required)
            tools = [
                {
                    "function_declarations": [
                        
                        {
                            "name": "submit_form_summary",
                            "description": "Submit a single concise overall summary of the conversation and a JSON (as text) representing the function-calling payload based on the user's inputs.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "summary_text": {"type": "string"},
                                    "function_call_json_text": {"type": "string"}
                                },
                                "required": ["summary_text", "function_call_json_text"]
                            }
                        },
                        {
                            "name": "complete_form",
                            "description": "Mark the form as completed when all required fields are captured.",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    ]
                }
            ]
            #have only one field, instead of several answers, dumb it down for gemini, ask for the entire convo summary and then pst hte tool call to text 
            # Config - Enable transcription to get text alongside audio
            config = {
                "system_instruction": system_instruction,
                "response_modalities": ["AUDIO"],
                "proactivity": {'proactive_audio': True},
                "tools": tools,
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": "Aoede"}
                    }
                },
                "realtime_input_config": {
                    "automatic_activity_detection": {
                        "silence_duration_ms": 3000
                    }
                }
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
                tg.create_task(self._monitor_silence())
                
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
                        try:
                            self._last_ai_audio_monotonic = asyncio.get_running_loop().time()
                        except Exception:
                            pass
                        self.audio_in_queue.put_nowait(data)
                        continue
                    
                    # Debug: Log the entire response structure
                    logger.info(f"Response type: {type(response)}")
                    logger.info(f"Response attributes: {dir(response)}")
                    
                    # Check response.text first (may be absent in audio-only mode)
                    text_content = None
                    if text := response.text:
                        text_content = text
                        logger.info(f"Found text in response.text: {text_content}")
                    
                    # Check server_content as fallback (Gemini sends text here!)
                    if hasattr(response, 'server_content') and response.server_content:
                        sc = response.server_content
                        logger.info(f"server_content type: {type(sc)}")
                        
                        # Check turn_complete status
                        if hasattr(sc, 'turn_complete'):
                            logger.info(f"turn_complete: {sc.turn_complete}")
                        
                        # Try model_turn
                        if hasattr(sc, 'model_turn'):
                            mt = sc.model_turn
                            logger.info(f"model_turn: {mt} (type: {type(mt)})")
                            
                            if mt and hasattr(mt, 'parts'):
                                logger.info(f"model_turn.parts: {len(mt.parts)} parts")
                                for i, part in enumerate(mt.parts):
                                    logger.info(f"Part {i}: {type(part)}")
                                    # Try to get text from part
                                    if hasattr(part, 'text'):
                                        text_content = part.text
                                        logger.info(f"✅ FOUND TEXT: {text_content}")
                                        break
                                    elif hasattr(part, 'inline_data'):
                                        logger.info(f"Part {i} has inline_data (audio)")
                        
                        # Try output_transcription as alternative
                        if not text_content and hasattr(sc, 'output_transcription'):
                            ot = sc.output_transcription
                            logger.info(f"output_transcription: {ot}")
                            if ot:
                                text_content = ot
                    
                    if text_content:
                        # Log and send transcript
                        logger.info(f"Gemini says: {text_content}")
                        self.conversation_history.append({'role': 'assistant', 'text': text_content})
                        
                        await self.send(text_data=json.dumps({
                            'type': 'transcript',
                            'text': text_content,
                            'speaker': 'assistant'
                        }))
                        
                        # Check if survey is complete
                        if self.is_survey_complete(text_content):
                            logger.info(f"Survey completion detected in text: {text_content}")
                            await self.handle_completion()

                    # Handle tool calls (structured extraction without transcripts) pass summary text from the arguments here to text llm then to front end
                    try:
                        # Normalize into a list of {'name': str, 'args': dict}
                        calls = self._extract_tool_calls(response)
                        for call in calls:
                            name = (call.get('name') or '').strip()
                            args = call.get('args') or {}
                            logger.info(f"Tool call received: {name} args={args}")

                            if name == 'save_field' and isinstance(args, dict):
                                field_name = self._get_ci(args, 'field_name', 'fieldName', 'name')
                                value = args.get('value')
                                if field_name:
                                    self.collected_data[field_name] = value
                                    # Update progress to client (best-effort)
                                    await self.send(text_data=json.dumps({
                                        'type': 'progress',
                                        'current_field': len([v for v in self.collected_data.values() if v is not None]),
                                        'total_fields': self.form_config.get('total_fields', 0),
                                        'percentage': int(100 * len([v for v in self.collected_data.values() if v is not None]) / max(self.form_config.get('total_fields', 1), 1))
                                    }))

                            elif name == 'submit_form_summary' and isinstance(args, dict):
                                summary_text = self._get_ci(args, 'summary_text', 'summaryText', 'summary') or ''
                                fc_json_text = self._get_ci(args, 'function_call_json_text', 'functionCallJsonText', 'json', 'payload') or '{}'
                                try:
                                    parsed = json.loads(fc_json_text)
                                    if isinstance(parsed, dict):
                                        self.collected_data.update(parsed)
                                except Exception:
                                    logger.warning("submit_form_summary function_call_json_text was not valid JSON")
                                await self.send(text_data=json.dumps({
                                    'type': 'summary_submitted',
                                    'summary': summary_text,
                                    'extracted_fields': self.collected_data
                                }))
                                try:
                                    self._summary_event.set()
                                except Exception:
                                    pass

                            elif name == 'complete_form':
                                await self.handle_completion()
                    except Exception as e:
                        logger.error(f"Error handling tool call: {e}")
                
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
    
    async def _monitor_silence(self):
        """Monitor incoming audio and auto-complete after sustained silence."""
        try:
            loop = asyncio.get_running_loop()
            while True:
                await asyncio.sleep(0.25)
                if self._silence_monitor_triggered:
                    break
                if not self._speech_detected:
                    continue  # wait until any speech has been detected
                if self._last_sound_monotonic is None:
                    continue
                now = loop.time()
                silent_ms = int((now - self._last_sound_monotonic) * 1000)
                # Also consider raw last client audio arrival to avoid missing quiet speech
                if self._last_client_audio_monotonic is not None:
                    client_gap_ms = int((now - self._last_client_audio_monotonic) * 1000)
                else:
                    client_gap_ms = silent_ms
                # Avoid completing while AI is speaking or just finished
                ai_gap_ms = int((now - (self._last_ai_audio_monotonic or 0)) * 1000)
                if silent_ms >= self._silence_timeout_ms and client_gap_ms >= self._silence_timeout_ms and ai_gap_ms > 1500:
                    logger.info(f"Silence > {self._silence_timeout_ms}ms detected; waiting for summary then auto-completing {self.session_id}.")
                    self._silence_monitor_triggered = True
                    # Grace period to allow model to send summary/tool calls
                    try:
                        await asyncio.wait_for(self._summary_event.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
                    try:
                        await self.handle_completion()
                    except Exception as e:
                        logger.error(f"Error during auto-completion: {e}")
                    break
        except asyncio.CancelledError:
            pass
    
    def _get_ci(self, mapping, *keys):
        """Case-insensitive, variant-friendly getter from dict-like args."""
        try:
            if not isinstance(mapping, dict):
                return None
            for k in keys:
                if k in mapping:
                    return mapping.get(k)
            lower_map = {str(k).lower(): v for k, v in mapping.items()}
            for k in keys:
                v = lower_map.get(str(k).lower())
                if v is not None:
                    return v
        except Exception:
            return None
        return None

    def _extract_tool_calls(self, response):
        """
        Normalize tool/function calls from various SDK response shapes into a list of
        { 'name': str, 'args': dict } items.
        """
        calls = []
        try:
            # Direct singular tool_call
            tc = getattr(response, 'tool_call', None)
            if tc:
                fc_list = getattr(tc, 'function_calls', None) or getattr(tc, 'tool_calls', None)
                if fc_list and isinstance(fc_list, (list, tuple)):
                    for fc in fc_list:
                        name = getattr(fc, 'name', None) or getattr(fc, 'function', None)
                        args = getattr(fc, 'args', None) or getattr(fc, 'parameters', None) or {}
                        if name:
                            calls.append({'name': name, 'args': args if isinstance(args, dict) else {}})
                else:
                    name = getattr(tc, 'name', None) or getattr(tc, 'function', None)
                    args = getattr(tc, 'args', None) or getattr(tc, 'parameters', None) or {}
                    if name:
                        calls.append({'name': name, 'args': args if isinstance(args, dict) else {}})

            # Plural attributes directly on response
            for attr in ('function_calls', 'tool_calls'):
                fc_list = getattr(response, attr, None)
                if fc_list and isinstance(fc_list, (list, tuple)):
                    for fc in fc_list:
                        name = getattr(fc, 'name', None) or getattr(fc, 'function', None)
                        args = getattr(fc, 'args', None) or getattr(fc, 'parameters', None) or {}
                        if name:
                            calls.append({'name': name, 'args': args if isinstance(args, dict) else {}})

            # server_content.model_turn.parts nested function/tool calls
            sc = getattr(response, 'server_content', None)
            if sc and hasattr(sc, 'model_turn') and getattr(sc.model_turn, 'parts', None):
                for part in sc.model_turn.parts:
                    for cand_attr in ('function_call', 'tool_call'):
                        fc = getattr(part, cand_attr, None)
                        if fc:
                            name = getattr(fc, 'name', None) or getattr(fc, 'function', None)
                            args = getattr(fc, 'args', None) or getattr(fc, 'parameters', None) or {}
                            if name:
                                calls.append({'name': name, 'args': args if isinstance(args, dict) else {}})
                    name = getattr(part, 'name', None) or getattr(part, 'function', None)
                    if name and (hasattr(part, 'args') or hasattr(part, 'parameters')):
                        args = getattr(part, 'args', None) or getattr(part, 'parameters', None) or {}
                        calls.append({'name': name, 'args': args if isinstance(args, dict) else {}})
        except Exception as e:
            logger.error(f"Error extracting tool calls: {e}")

        # Debug: log consolidated calls for visibility
        if calls:
            try:
                logger.info(f"Consolidated tool calls: {[c.get('name') for c in calls]}")
            except Exception:
                pass
        return calls

    def build_system_instruction(self):
        """Build system instruction for form"""
        fields = self.form_config['fields']
        field_list = []
        
        for i, field in enumerate(fields, 1):
            req = "REQUIRED" if field.get('required') else "optional"
            field_list.append(
                f"{i}. {field['name']} ({field['type']}, {req}): {field['prompt']}"
            )
        
        # Get first question
        first_field = fields[0] if fields else None
        first_prompt = first_field['prompt'] if first_field else "Hello!"
        
        return f"""You are a friendly conversational assistant guiding a short voice form.

PRIMARY GOAL:
- Keep a natural, brief conversation to gather the necessary information.
- Prefer a single summary-first submission at the end via submit_form_summary.

AVAILABLE QUESTIONS (use them as guidance, but keep it conversational):
{chr(10).join(field_list)}

START NOW by saying ONLY this opening line:
"{self.form_config.get('ai_prompt', 'Hello!')} {first_prompt}"

STYLE RULES:
- Keep replies concise.
- Be friendly and on-topic.

COMPLETION RULES (CRITICAL):
- When you have enough information, call submit_form_summary with parameters:
  {{"summary_text": "<1-2 sentence concise summary>", "function_call_json_text": "<JSON string representing the extracted answers>"}}
- The function_call_json_text MUST be valid JSON string with keys matching field names and correct types.
- After calling submit_form_summary, say EXACTLY: "Thank you! Survey complete." and then call complete_form.

LEGACY FALLBACK (only if necessary):
- If required, you MAY call save_field per question, then call complete_form when done.
"""
    
    def is_survey_complete(self, text):
        """Check if survey is complete based on Gemini's response"""
        # Check for completion phrases
        text_lower = text.lower()
        completion_phrases = [
            'survey complete',
            'survey complere',  # typo handling
            'thank you! survey',
            'that completes',
            'all done'
        ]
        is_complete = any(phrase in text_lower for phrase in completion_phrases)
        if is_complete:
            logger.info(f"✅ COMPLETION PHRASE DETECTED: '{text}'")
        return is_complete
    
    async def handle_completion(self):
        """Handle survey completion"""
        try:
            logger.info(f"Survey completed for session {self.session_id}")
            
            # Save conversation history as collected data
            await self.save_conversation()
            
            # Extract structured fields + summary via Gemini (Option B)
            extraction = ai_service.extract_structured_from_conversation(
                self.form_config.get('fields', []),
                self.conversation_history
            )
            summary = extraction.get('summary_text')
            extracted_fields = extraction.get('fields') or {}

            # Fallbacks if extraction returns little/none
            if not extracted_fields and self.collected_data:
                extracted_fields = dict(self.collected_data)
            if not summary:
                if extracted_fields:
                    # Build a compact "k: v; ..." summary
                    try:
                        pairs = [f"{k}: {extracted_fields.get(k)}" for k in extracted_fields.keys()]
                        summary = "; ".join(pairs)
                    except Exception:
                        summary = ai_service.summarize_conversation(self.conversation_history)
                else:
                    summary = ai_service.summarize_conversation(self.conversation_history)
            
            # Merge with values captured via tool calls. Prefer non-null from collected_data
            if self.collected_data:
                merged_fields = dict(extracted_fields or {})
                try:
                    for k, v in self.collected_data.items():
                        if v is not None and v != '':
                            merged_fields[k] = v
                    extracted_fields = merged_fields
                except Exception:
                    pass

            # Ensure in-memory collected_data reflects the merged fields before saving
            try:
                if extracted_fields:
                    self.collected_data.update(extracted_fields)
            except Exception:
                pass

            # Build a friendly AI-generated summary from merged fields when available,
            # otherwise fall back to conversation-based summary.
            try:
                if extracted_fields:
                    summary = ai_service.summarize_fields(
                        extracted_fields,
                        form_title=self.form_config.get('form_name')
                    )
                if not summary:
                    summary = ai_service.summarize_conversation(self.conversation_history)
            except Exception:
                summary = ai_service.summarize_conversation(self.conversation_history)

            # Persist summary for this session
            try:
                await self.save_summary_text(summary)
            except Exception as e:
                logger.warning(f"Failed to save summary_text: {e}")

            # Mark session as completed
            await self.mark_session_completed()
            
            # Send completion message
            await self.send(text_data=json.dumps({
                'type': 'completed',
                'message': self.form_config.get('success_message', 'Thank you! Survey completed.'),
                'conversation': self.conversation_history,
                'summary': summary,
                'extracted_fields': extracted_fields,
                'confidence': extraction.get('confidence', 0)
            }))
            
            # Trigger webhook
            await self.trigger_webhook()
        except Exception as e:
            logger.error(f"Error in handle_completion: {e}", exc_info=True)
    
    @database_sync_to_async
    def save_conversation(self):
        """Save conversation history to database"""
        try:
            session = MagicLinkSession.objects.get(session_id=self.session_id)
            session.conversation_history = self.conversation_history
            session.save()
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")

    @database_sync_to_async
    def save_summary_text(self, summary):
        """Save LLM summary to the session."""
        try:
            session = MagicLinkSession.objects.get(session_id=self.session_id)
            session.summary_text = summary or ''
            session.save(update_fields=['summary_text'])
        except Exception as e:
            logger.error(f"Error saving summary_text: {e}")
    
    @database_sync_to_async
    def mark_session_completed(self):
        """Mark session as completed"""
        try:
            session = MagicLinkSession.objects.get(session_id=self.session_id)
            session.status = 'completed'
            session.completed_at = timezone.now()
            if not session.collected_data:
                session.collected_data = self.collected_data
            session.save()
        except Exception as e:
            logger.error(f"Error marking session complete: {e}")
    
    @database_sync_to_async
    def trigger_webhook(self):
        """Trigger webhook delivery"""
        try:
            session = MagicLinkSession.objects.get(session_id=self.session_id)
            form_config = session.form_config
            webhook_url = getattr(form_config, 'webhook_url', None) or form_config.webhook_config.get('url') if hasattr(form_config, 'webhook_config') else None
            
            if webhook_url:
                # Trigger async task
                send_webhook.delay(session.session_id)
                logger.info(f"Webhook triggered for session {self.session_id}")
            else:
                logger.info(f"No webhook configured for session {self.session_id}")
        except Exception as e:
            logger.error(f"Error triggering webhook: {e}")
    
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
