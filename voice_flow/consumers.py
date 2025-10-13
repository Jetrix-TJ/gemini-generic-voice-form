"""
WebSocket consumers for real-time voice processing
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import MagicLinkSession, VoiceFormConfig
from .ai_service import ai_service
from .tasks import send_webhook

logger = logging.getLogger(__name__)


class VoiceConversationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling voice conversation
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'voice_session_{self.session_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Accept connection
        await self.accept()
        
        # Initialize session
        try:
            session_data = await self.get_session_data()
            if session_data['is_valid']:
                # Send initial greeting
                await self.send_message({
                    'type': 'greeting',
                    'message': await self.generate_greeting(session_data),
                    'form_name': session_data['form_name'],
                    'total_fields': session_data['total_fields']
                })
            else:
                await self.send_message({
                    'type': 'error',
                    'message': session_data.get('error', 'Invalid session')
                })
                await self.close()
        except Exception as e:
            logger.error(f"Error initializing session {self.session_id}: {e}")
            await self.send_message({
                'type': 'error',
                'message': 'Failed to initialize session'
            })
            await self.close()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive message from WebSocket
        
        Expected message format:
        {
            "type": "audio" | "text" | "start_field" | "skip_field",
            "data": <message data>,
            "field_name": <optional field name>
        }
        """
        try:
            if text_data:
                data = json.loads(text_data)
                message_type = data.get('type')
                
                if message_type == 'text':
                    await self.handle_text_input(data)
                elif message_type == 'audio':
                    await self.handle_audio_input(data)
                elif message_type == 'start_field':
                    await self.handle_start_field(data)
                elif message_type == 'skip_field':
                    await self.handle_skip_field(data)
                elif message_type == 'complete':
                    await self.handle_completion()
                else:
                    logger.warning(f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            await self.send_message({
                'type': 'error',
                'message': 'Invalid message format'
            })
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send_message({
                'type': 'error',
                'message': 'An error occurred processing your message'
            })
    
    async def handle_text_input(self, data):
        """Handle text input from user"""
        user_text = data.get('data', '')
        
        if not user_text:
            return
        
        # Get current field
        session_data = await self.get_session_data()
        current_field = await self.get_current_field(session_data)
        
        if not current_field:
            # All fields completed
            await self.handle_completion()
            return
        
        # Save user message to conversation
        await self.add_conversation_message('user', user_text, current_field['name'])
        
        # Process with AI
        result = await self.process_with_ai(
            user_text,
            current_field,
            session_data
        )
        
        # Save AI response to conversation
        await self.add_conversation_message('assistant', result['ai_response'], current_field['name'])
        
        if result['is_valid']:
            # Save the extracted value
            await self.save_field_value(current_field['name'], result['value'])
            
            # Send success response
            await self.send_message({
                'type': 'field_completed',
                'field_name': current_field['name'],
                'value': result['value'],
                'ai_response': result['ai_response'],
                'progress': await self.get_progress()
            })
            
            # Check if all fields are completed
            if await self.all_fields_completed():
                await self.handle_completion()
            else:
                # Move to next field
                next_field = await self.get_next_field(session_data)
                await self.send_message({
                    'type': 'next_field',
                    'field': next_field,
                    'ai_prompt': await self.generate_field_prompt(next_field, session_data)
                })
        else:
            # Send retry message
            await self.send_message({
                'type': 'field_retry',
                'field_name': current_field['name'],
                'ai_response': result['ai_response'],
                'error': result.get('error')
            })
    
    async def handle_audio_input(self, data):
        """
        Handle audio input from user
        Note: Audio would need to be transcribed first (e.g., using Web Speech API on client side)
        For now, we expect pre-transcribed text in the data
        """
        transcribed_text = data.get('data', '')
        
        # Process as text input
        await self.handle_text_input({
            'type': 'text',
            'data': transcribed_text
        })
    
    async def handle_start_field(self, data):
        """Handle request to start/restart a specific field"""
        field_name = data.get('field_name')
        
        session_data = await self.get_session_data()
        field = await self.get_field_by_name(session_data, field_name)
        
        if field:
            prompt = await self.generate_field_prompt(field, session_data)
            await self.send_message({
                'type': 'field_prompt',
                'field': field,
                'ai_prompt': prompt
            })
    
    async def handle_skip_field(self, data):
        """Handle skipping a non-required field"""
        field_name = data.get('field_name')
        
        session_data = await self.get_session_data()
        field = await self.get_field_by_name(session_data, field_name)
        
        if field and not field.get('required'):
            await self.save_field_value(field_name, None)
            
            # Move to next field
            next_field = await self.get_next_field(session_data)
            if next_field:
                await self.send_message({
                    'type': 'next_field',
                    'field': next_field,
                    'ai_prompt': await self.generate_field_prompt(next_field, session_data)
                })
            else:
                await self.handle_completion()
    
    async def handle_completion(self):
        """Handle form completion"""
        # Mark session as completed
        await self.mark_session_completed()
        
        # Get final data
        session_data = await self.get_session_data()
        
        # Send completion message
        await self.send_message({
            'type': 'completed',
            'message': session_data['success_message'],
            'collected_data': session_data['collected_data'],
            'duration_seconds': session_data.get('duration_seconds')
        })
        
        # Trigger webhook
        await self.trigger_webhook()
    
    async def send_message(self, message):
        """Send message to WebSocket"""
        await self.send(text_data=json.dumps(message))
    
    # Database operations (sync to async)
    
    @database_sync_to_async
    def get_session_data(self):
        """Get session and form configuration data"""
        try:
            session = MagicLinkSession.objects.select_related('form_config').get(
                session_id=self.session_id
            )
            
            # Check if expired
            if session.is_expired():
                return {
                    'is_valid': False,
                    'error': 'Session has expired'
                }
            
            # Check if already completed
            if session.status == 'completed':
                return {
                    'is_valid': False,
                    'error': 'Session already completed'
                }
            
            form_config = session.form_config
            
            return {
                'is_valid': True,
                'session_id': session.session_id,
                'form_id': form_config.form_id,
                'form_name': form_config.name,
                'form_description': form_config.description,
                'ai_prompt': form_config.ai_prompt,
                'fields': form_config.fields,
                'total_fields': len(form_config.fields),
                'collected_data': session.collected_data,
                'conversation_history': session.conversation_history,
                'success_message': form_config.success_message,
                'settings': form_config.settings,
                'session_data': session.session_data,
                'duration_seconds': session.duration_seconds
            }
        except MagicLinkSession.DoesNotExist:
            return {
                'is_valid': False,
                'error': 'Session not found'
            }
    
    @database_sync_to_async
    def add_conversation_message(self, role, content, field_name=None):
        """Add message to conversation history"""
        session = MagicLinkSession.objects.get(session_id=self.session_id)
        session.add_conversation_message(role, content, field_name)
    
    @database_sync_to_async
    def save_field_value(self, field_name, value):
        """Save field value to session"""
        session = MagicLinkSession.objects.get(session_id=self.session_id)
        session.update_collected_data(field_name, value)
    
    @database_sync_to_async
    def mark_session_completed(self):
        """Mark session as completed"""
        session = MagicLinkSession.objects.get(session_id=self.session_id)
        session.mark_completed()
    
    @database_sync_to_async
    def get_progress(self):
        """Get current progress"""
        session = MagicLinkSession.objects.get(session_id=self.session_id)
        return {
            'fields_completed': session.fields_completed,
            'total_fields': len(session.form_config.fields),
            'percentage': session.get_completion_percentage()
        }
    
    @database_sync_to_async
    def all_fields_completed(self):
        """Check if all required fields are completed"""
        session = MagicLinkSession.objects.get(session_id=self.session_id)
        form_config = session.form_config
        
        required_fields = [f['name'] for f in form_config.fields if f.get('required')]
        collected = session.collected_data
        
        return all(field in collected and collected[field] is not None for field in required_fields)
    
    @database_sync_to_async
    def trigger_webhook(self):
        """Trigger webhook delivery"""
        send_webhook.delay(self.session_id)
    
    # AI helper methods
    
    async def generate_greeting(self, session_data):
        """Generate initial greeting message"""
        return ai_service.generate_ai_message(session_data['ai_prompt'])
    
    async def get_current_field(self, session_data):
        """Get the current field to process"""
        collected = session_data['collected_data']
        for field in session_data['fields']:
            if field['name'] not in collected:
                return field
        return None
    
    async def get_next_field(self, session_data):
        """Get the next field after current"""
        collected = session_data['collected_data']
        found_current = False
        
        for field in session_data['fields']:
            if field['name'] in collected:
                found_current = True
                continue
            if found_current or field['name'] not in collected:
                return field
        
        return None
    
    async def get_field_by_name(self, session_data, field_name):
        """Get field definition by name"""
        for field in session_data['fields']:
            if field['name'] == field_name:
                return field
        return None
    
    @database_sync_to_async
    def process_with_ai(self, user_input, field_def, session_data):
        """Process user input with AI"""
        conversation_context = json.dumps(session_data['conversation_history'][-5:])
        return ai_service.process_user_input(user_input, field_def, conversation_context)
    
    @database_sync_to_async
    def generate_field_prompt(self, field, session_data):
        """Generate AI prompt for a field"""
        prompt = ai_service.generate_conversation_prompt(
            {
                'name': session_data['form_name'],
                'description': session_data['form_description'],
                'ai_prompt': session_data['ai_prompt']
            },
            field,
            session_data['collected_data'],
            session_data['conversation_history']
        )
        return ai_service.generate_ai_message(prompt)

