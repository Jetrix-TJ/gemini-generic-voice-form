"""
AI Service Integration for Voice Processing

Supports:
- Gemini 2.5 Flash Native Audio (Live API - recommended)
- Gemini 2.0 Flash (latest experimental with native audio)
- Gemini 1.5 Pro (stable with multimodal support)
- Gemini 1.5 Flash (fast with audio capabilities)

For real-time voice, use the Live API (live_audio_service.py)
For text-based interactions, this service provides fallback support.
"""
import json
import logging
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Try to import google-genai (new SDK for Live API)
try:
    from google import genai
    GENAI_AVAILABLE = True
    logger.info("Using google-genai (Live API SDK)")
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    logger.warning("google-genai not available. Install with: pip install google-genai")


class AIService:
    """Service for AI-powered voice conversation"""
    
    def __init__(self):
        self.gemini_api_key = settings.VOICE_FORM_SETTINGS.get('GEMINI_API_KEY')
        self.model = None
        
        if not self.gemini_api_key:
            logger.warning("GEMINI_API_KEY not configured")
            return
        
        if not GENAI_AVAILABLE:
            logger.warning("google-genai not installed. AI service disabled.")
            logger.info("Install with: pip install google-genai")
            return
        
        try:
            # Create client for API access
            self.client = genai.Client(api_key=self.gemini_api_key)
            self.model = "text-mode"  # Placeholder - this service is mainly for fallback
            logger.info(f"Initialized Gemini client (fallback mode)")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.model = None
    
    def generate_conversation_prompt(self, form_config: Dict, current_field: Dict, 
                                    collected_data: Dict, conversation_history: list) -> str:
        """Generate a prompt for the AI based on current context"""
        
        # Build context
        context_parts = [
            "You are a friendly AI assistant helping users fill out a form through natural voice conversation.",
            f"\nForm Purpose: {form_config.get('description', form_config.get('name'))}",
            f"\nInitial Greeting: {form_config.get('ai_prompt', '')}",
        ]
        
        # Add conversation history context
        if conversation_history:
            context_parts.append("\nConversation so far:")
            for msg in conversation_history[-5:]:  # Last 5 messages
                role = "AI" if msg['role'] == 'assistant' else "User"
                context_parts.append(f"{role}: {msg['content']}")
        
        # Add current field context
        if current_field:
            context_parts.append(f"\nCurrent Field: {current_field['name']}")
            context_parts.append(f"Field Type: {current_field['type']}")
            context_parts.append(f"Required: {'Yes' if current_field.get('required') else 'No'}")
            context_parts.append(f"Prompt to ask: {current_field['prompt']}")
            
            # Add validation rules
            validation = current_field.get('validation', {})
            if validation:
                context_parts.append("Validation rules:")
                if 'options' in validation:
                    context_parts.append(f"- Valid options: {', '.join(validation['options'])}")
                if 'min' in validation:
                    context_parts.append(f"- Minimum value: {validation['min']}")
                if 'max' in validation:
                    context_parts.append(f"- Maximum value: {validation['max']}")
        
        # Add collected data
        if collected_data:
            context_parts.append("\nData collected so far:")
            for key, value in collected_data.items():
                context_parts.append(f"- {key}: {value}")
        
        # Add instructions
        context_parts.extend([
            "\nInstructions:",
            "1. Ask the current field's question in a natural, conversational way",
            "2. Be friendly, patient, and helpful",
            "3. If the user's response doesn't match the expected format, politely ask them to try again",
            "4. Keep responses concise and clear",
            "5. Use the user's previous responses to make the conversation flow naturally",
            "\nRespond with your next message to the user:"
        ])
        
        return "\n".join(context_parts)
    
    def process_user_input(self, user_input: str, field_def: Dict, 
                          conversation_context: str) -> Dict[str, Any]:
        """
        Process user's voice input and extract structured data
        
        Returns:
            Dict with keys:
            - 'value': Extracted value for the field
            - 'is_valid': Boolean indicating if input is valid
            - 'ai_response': AI's response to the user
            - 'error': Error message if any
        """
        if not self.model:
            return {
                'value': user_input,
                'is_valid': True,
                'ai_response': "Thank you. Let's continue.",
                'error': None
            }
        
        try:
            # Create extraction prompt
            extraction_prompt = self._create_extraction_prompt(user_input, field_def, conversation_context)
            
            # Call AI model
            response = self.model.generate_content(extraction_prompt)
            response_text = response.text.strip()
            
            # Parse response
            result = self._parse_ai_response(response_text, field_def)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return {
                'value': user_input,
                'is_valid': False,
                'ai_response': "I'm sorry, I didn't quite understand that. Could you please repeat?",
                'error': str(e)
            }
    
    def _create_extraction_prompt(self, user_input: str, field_def: Dict, context: str) -> str:
        """Create prompt for extracting structured data from user input"""
        
        field_type = field_def['type']
        field_name = field_def['name']
        validation = field_def.get('validation', {})
        
        prompt_parts = [
            f"Extract the {field_type} value for the field '{field_name}' from the user's response.",
            f"\nUser's response: \"{user_input}\"",
            f"\nField type: {field_type}",
        ]
        
        # Add validation context
        if 'options' in validation:
            prompt_parts.append(f"Valid options: {', '.join(validation['options'])}")
            prompt_parts.append("The user's response should match one of these options (case-insensitive).")
        
        if field_type == 'number':
            if 'min' in validation:
                prompt_parts.append(f"Minimum value: {validation['min']}")
            if 'max' in validation:
                prompt_parts.append(f"Maximum value: {validation['max']}")
        
        if field_type == 'boolean':
            prompt_parts.append("Convert yes/no/true/false responses to boolean.")
        
        # Add output format instructions
        prompt_parts.extend([
            "\nRespond in JSON format with exactly these fields:",
            "{",
            '  "value": <extracted value or null if invalid>,',
            '  "is_valid": <true or false>,',
            '  "ai_response": "<your response to the user>",',
            '  "confidence": <0-100>',
            "}",
            "\nIf the input is valid:",
            "- Extract the value and set is_valid to true",
            "- Respond with a friendly confirmation",
            "\nIf the input is invalid or unclear:",
            "- Set value to null and is_valid to false",
            "- Respond with a friendly request to clarify or try again",
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_ai_response(self, response_text: str, field_def: Dict) -> Dict[str, Any]:
        """Parse AI's JSON response"""
        try:
            # Extract JSON from response (in case there's extra text)
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                data = json.loads(json_str)
                
                return {
                    'value': data.get('value'),
                    'is_valid': data.get('is_valid', False),
                    'ai_response': data.get('ai_response', 'Thank you.'),
                    'error': None
                }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
        
        # Fallback: treat response as the AI's message
        return {
            'value': None,
            'is_valid': False,
            'ai_response': response_text if response_text else "Could you please repeat that?",
            'error': "Failed to parse structured response"
        }
    
    def generate_ai_message(self, prompt: str) -> Optional[str]:
        """Generate an AI message from a prompt (fallback mode)"""
        if not self.model or not GENAI_AVAILABLE:
            return "Hello! I'm here to help you fill out this form."
        
        try:
            # Use the Live API in text mode for simple responses
            # In practice, this would use the Live API's text capabilities
            # For now, return a simple response
            return "Hello! Let's get started with your form."
        except Exception as e:
            logger.error(f"Error generating AI message: {e}")
            return "Hello! Let's get started with your form."
    
    def process_audio_input(self, audio_data: bytes, mime_type: str, field_def: Dict) -> Dict[str, Any]:
        """
        Process audio input directly with Gemini (native audio support)
        
        Args:
            audio_data: Raw audio bytes
            mime_type: Audio MIME type (e.g., 'audio/wav', 'audio/webm')
            field_def: Field definition
            
        Returns:
            Dict with extracted value and AI response
        """
        if not self.model:
            return {
                'value': None,
                'is_valid': False,
                'ai_response': 'AI service not configured',
                'error': 'Missing API key'
            }
        
        try:
            # Create prompt for audio processing
            prompt_text = f"""
            Listen to the audio and extract the answer for this question:
            Question: {field_def['prompt']}
            Field type: {field_def['type']}
            Required: {field_def.get('required', False)}
            
            Provide a JSON response with:
            - "value": the extracted answer
            - "is_valid": whether the answer is valid
            - "ai_response": a friendly confirmation or request for clarification
            """
            
            # Upload audio file
            audio_file = genai.upload_file(
                path=audio_data,
                mime_type=mime_type
            )
            
            # Generate response with audio
            response = self.model.generate_content([prompt_text, audio_file])
            
            # Parse response
            return self._parse_ai_response(response.text, field_def)
            
        except Exception as e:
            logger.error(f"Error processing audio with Gemini: {e}")
            return {
                'value': None,
                'is_valid': False,
                'ai_response': 'Sorry, I had trouble processing the audio. Could you try again?',
                'error': str(e)
            }
    
    def validate_field_value(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """
        Validate a field value against its definition
        
        Returns:
            Dict with 'is_valid' and 'error_message' keys
        """
        field_type = field_def['type']
        validation = field_def.get('validation', {})
        required = field_def.get('required', False)
        
        # Check required
        if required and (value is None or value == ''):
            return {
                'is_valid': False,
                'error_message': 'This field is required'
            }
        
        if value is None or value == '':
            return {'is_valid': True, 'error_message': None}
        
        # Type-specific validation
        if field_type == 'number':
            try:
                num_value = float(value)
                if validation.get('integer_only') and not isinstance(value, int):
                    return {'is_valid': False, 'error_message': 'Must be an integer'}
                if 'min' in validation and num_value < validation['min']:
                    return {'is_valid': False, 'error_message': f"Must be at least {validation['min']}"}
                if 'max' in validation and num_value > validation['max']:
                    return {'is_valid': False, 'error_message': f"Must be at most {validation['max']}"}
            except (ValueError, TypeError):
                return {'is_valid': False, 'error_message': 'Must be a number'}
        
        elif field_type == 'email':
            if '@' not in str(value) or '.' not in str(value):
                return {'is_valid': False, 'error_message': 'Invalid email format'}
        
        elif field_type in ['choice', 'multi_choice']:
            options = validation.get('options', [])
            if options and value not in options:
                return {'is_valid': False, 'error_message': f"Must be one of: {', '.join(options)}"}
        
        return {'is_valid': True, 'error_message': None}


# Singleton instance
ai_service = AIService()

