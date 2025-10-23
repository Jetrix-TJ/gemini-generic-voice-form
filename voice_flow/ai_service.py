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
            # Create client for API access (use v1alpha to support experimental models)
            self.client = genai.Client(api_key=self.gemini_api_key, http_options={"api_version": "v1alpha"})
            # Select a TEXT model for structured extraction (never use audio preview IDs)
            configured_text = settings.VOICE_FORM_SETTINGS.get('GEMINI_TEXT_MODEL')
            configured_generic = settings.VOICE_FORM_SETTINGS.get('GEMINI_MODEL')
            # Prefer explicit text model; otherwise prefer generic if it doesn't look like an audio model
            if configured_text:
                self.text_model_id = configured_text
            elif configured_generic and 'audio' not in configured_generic.lower():
                self.text_model_id = configured_generic
            else:
                # Safe default text model
                self.text_model_id = 'gemini-2.0-flash-exp'
            # Keep a flag; the class' previous 'model' is not required for text calls
            self.model = None
            logger.info(f"Initialized Gemini client (text model: {self.text_model_id})")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.model = None
    
    def generate_conversation_prompt(self, form_config: Dict, current_field: Dict, 
                                    collected_data: Dict, conversation_history: list) -> str:
        """Generate a prompt for the AI based on current context"""
        # add seperate function schema for the whole summary of the conversation. 
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

    def generate_form_schema(self, form_desc: str, conversation_history: Optional[list] = None) -> Dict[str, Any]:
        """Generate a form schema from a natural-language description.

        Args:
            form_desc: Free-text description of the desired form (do not call this 'summary').
            conversation_history: Optional prior messages to provide additional context.

        Returns:
            Dict with keys:
            - 'schema': { 'name', 'description', 'ai_prompt', 'fields': [...] }
            - 'clarifying_questions': [] when confident, else list of questions
        """
        desc = (form_desc or '').strip()
        if not desc:
            return {
                'schema': None,
                'clarifying_questions': [
                    'Please describe the purpose, audience, and key fields of your form.'
                ]
            }

        # Fallback when SDK unavailable
        if not GENAI_AVAILABLE or not getattr(self, 'client', None):
            return {
                'schema': self._heuristic_schema_from_desc(desc),
                'clarifying_questions': []
            }

        # Build strict JSON instruction
        json_shape = (
            '{\n'
            '  "name": "<short human-readable form name>",\n'
            '  "description": "<1-2 sentences>",\n'
            '  "ai_prompt": "<brief friendly greeting to start>",\n'
            '  "fields": [\n'
            '    {\n'
            '      "name": "<snake_case>",\n'
            '      "type": "text|number|email|phone|date|boolean|choice|multi_choice",\n'
            '      "required": true,\n'
            '      "prompt": "<concise question>",\n'
            '      "validation": { }\n'
            '    }\n'
            '  ]\n'
            '}'
        )

        convo = ''
        if conversation_history:
            try:
                last_msgs = conversation_history[-10:]
                convo_lines = []
                for m in last_msgs:
                    role = m.get('role', 'user') if isinstance(m, dict) else 'user'
                    text = (m.get('content') or m.get('text') or '') if isinstance(m, dict) else str(m)
                    if text:
                        convo_lines.append(f"{role.upper()}: {text}")
                convo = "\n".join(convo_lines)
            except Exception:
                convo = ''

        prompt = (
            "You are a product assistant that converts a natural description into a minimal voice form schema.\n"
            "Respond with ONLY valid JSON. Do not include markdown.\n\n"
            f"Description:\n{desc}\n\n"
            f"Additional context (optional):\n{convo}\n\n"
            "Rules:\n"
            "- Prefer 3-8 essential fields.\n"
            "- Use correct types and minimal validation (min/max/options).\n"
            "- Prompts must be short, user-friendly questions.\n"
            "- Use snake_case for field names.\n"
            "- If the description is ambiguous, include no more than 3 clarifying questions separately.\n\n"
            "Respond in TWO JSON objects concatenated, separated by a newline:\n"
            "1) schema with this exact shape:\n" + json_shape + "\n"
            "2) clarifications with this shape:\n{\n  \"clarifying_questions\": [\"<q1>\", \"<q2>\"]\n}"
        )

        try:
            resp = self.client.models.generate_content(
                model=self.text_model_id,
                contents=prompt
            )
            text = None
            if hasattr(resp, 'text') and resp.text:
                text = resp.text
            else:
                cand = getattr(resp, 'candidates', None)
                if cand and len(cand) and hasattr(cand[0], 'content'):
                    parts = getattr(cand[0].content, 'parts', None)
                    if parts and len(parts) and hasattr(parts[0], 'text'):
                        text = parts[0].text
            if not text:
                raise ValueError('Empty Gemini response')

            # Attempt to parse two JSON objects; fallback to first found
            objs = []
            buf = text
            while True:
                s = buf.find('{')
                e = buf.find('}', s) + 1 if s >= 0 else -1
                if s < 0 or e <= s:
                    break
                # Expand to the last matching brace for robustness
                depth = 0
                end_idx = -1
                for i, ch in enumerate(buf[s:], start=s):
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break
                if end_idx == -1:
                    break
                try:
                    objs.append(json.loads(buf[s:end_idx]))
                except Exception:
                    pass
                buf = buf[end_idx:]

            schema_obj = None
            clarifs_obj = None
            for o in objs:
                if isinstance(o, dict) and 'fields' in o:
                    schema_obj = o
                if isinstance(o, dict) and 'clarifying_questions' in o:
                    clarifs_obj = o

            if not schema_obj:
                raise ValueError('No schema JSON found in response')

            clarifying_questions = (clarifs_obj or {}).get('clarifying_questions') or []
            # Final sanity: ensure keys exist
            schema_obj.setdefault('name', 'Untitled Form')
            schema_obj.setdefault('description', desc[:160])
            schema_obj.setdefault('ai_prompt', "Hello! Let's get started.")
            schema_obj.setdefault('fields', [])

            return {
                'schema': schema_obj,
                'clarifying_questions': clarifying_questions[:3]
            }
        except Exception as e:
            logger.error(f"Gemini schema generation failed: {e}")
            return {
                'schema': self._heuristic_schema_from_desc(desc),
                'clarifying_questions': []
            }

    def _heuristic_schema_from_desc(self, desc: str) -> Dict[str, Any]:
        """Very small heuristic generator used when Gemini is unavailable."""
        desc_l = desc.lower()
        fields = []
        def add_field(name, ftype, prompt, required=True, validation=None):
            f = {
                'name': name,
                'type': ftype,
                'required': required,
                'prompt': prompt,
            }
            if validation:
                f['validation'] = validation
            fields.append(f)

        # Common intents
        if 'job' in desc_l or 'application' in desc_l:
            add_field('full_name', 'text', 'What is your full name?', True)
            add_field('email', 'email', 'What is your email?', True)
            add_field('years_experience', 'number', 'How many years of experience do you have?', True, {'min': 0})
            add_field('portfolio_url', 'text', 'What is your portfolio URL?', False)
            name = 'Job Application'
        elif 'feedback' in desc_l or 'survey' in desc_l:
            add_field('full_name', 'text', 'What is your name?', False)
            add_field('email', 'email', 'What is your email?', False)
            add_field('rating', 'number', 'Rate your experience from 1 to 5.', True, {'min': 1, 'max': 5})
            add_field('comments', 'text', 'Any comments to share?', False, {'max_length': 500})
            name = 'Customer Feedback'
        else:
            add_field('full_name', 'text', 'What is your name?', True)
            add_field('email', 'email', 'What is your email?', True)
            add_field('phone_number', 'phone', 'What is your phone number?', False)
            name = 'Custom Form'

        return {
            'name': name,
            'description': desc[:200],
            'ai_prompt': "Hello! I'd love to ask a few quick questions.",
            'fields': fields
        }

    def summarize_conversation(self, conversation_history: list, max_chars: int = 600) -> str:
        """Create a concise text summary of the conversation without requiring transcription services.

        If no user transcripts are available, summarizes assistant prompts and system milestones.
        """
        if not conversation_history:
            return "No conversation available."

        # Normalize messages: support keys 'content' or 'text'
        def extract_text(msg):
            if isinstance(msg, dict):
                return str(msg.get('content') or msg.get('text') or '').strip()
            return str(msg)

        # Take last ~20 entries for brevity
        recent = conversation_history[-20:]
        assistant_lines = []
        user_lines = []
        for msg in recent:
            role = (msg.get('role') if isinstance(msg, dict) else None) or ''
            text = extract_text(msg)
            if not text:
                continue
            if role == 'assistant':
                assistant_lines.append(text)
            elif role == 'user':
                user_lines.append(text)

        bullets = []
        if user_lines:
            bullets.append("User responses captured: " + "; ".join(user_lines[:5]))
        if assistant_lines:
            bullets.append("Assistant prompts: " + "; ".join(assistant_lines[:5]))
        if not bullets:
            bullets.append("Conversation contained assistant prompts without user transcripts.")

        summary = "; ".join(bullets)
        if len(summary) > max_chars:
            summary = summary[: max_chars - 3] + "..."
        return summary

    def summarize_fields(self, fields: Dict[str, Any], form_title: Optional[str] = None, max_chars: int = 240) -> str:
        """Create a friendly one-sentence summary from structured fields.

        Prioritizes brevity and avoids mentioning missing/unknown values.
        """
        # Normalize fields: drop null/empty
        safe_fields = {}
        try:
            for k, v in (fields or {}).items():
                if v is None:
                    continue
                if isinstance(v, str) and not v.strip():
                    continue
                safe_fields[str(k)] = v
        except Exception:
            safe_fields = fields or {}

        if not safe_fields:
            return "No responses provided."

        # Fallback if SDK not available
        if not GENAI_AVAILABLE or not getattr(self, 'client', None):
            # Compact deterministic summary
            try:
                pairs = [f"{k}: {safe_fields.get(k)}" for k in safe_fields.keys()]
                text = "; ".join(pairs)
                if len(text) > max_chars:
                    text = text[: max_chars - 3] + "..."
                return text
            except Exception:
                return "; ".join(f"{k}: {v}" for k, v in list(safe_fields.items())[:6])

        title = (form_title or "Form submission").strip()
        fields_lines = "\n".join([f"- {k}: {safe_fields[k]}" for k in safe_fields.keys()])

        prompt = (
            f"You are given structured answers from a short voice form called '{title}'.\n"
            "Write a friendly one-sentence summary (optionally two if needed).\n"
            "Rules:\n"
            "- Include only provided values; do NOT mention missing info.\n"
            "- No quotes around values, no disclaimers, no bullet points.\n"
            "- Keep under 160 characters if possible.\n\n"
            f"Fields:\n{fields_lines}\n\n"
            "Now output just the summary sentence(s)."
        )

        try:
            resp = self.client.models.generate_content(
                model=self.text_model_id,
                contents=prompt
            )
            text = None
            if hasattr(resp, 'text') and resp.text:
                text = resp.text.strip()
            else:
                cand = getattr(resp, 'candidates', None)
                if cand and len(cand) and hasattr(cand[0], 'content'):
                    parts = getattr(cand[0].content, 'parts', None)
                    if parts and len(parts) and hasattr(parts[0], 'text'):
                        text = parts[0].text.strip()
            if not text:
                raise ValueError('Empty Gemini response')
            if len(text) > max_chars:
                text = text[: max_chars - 3] + "..."
            return text
        except Exception as e:
            logger.error(f"Gemini fields summary failed: {e}")
            # Deterministic fallback
            try:
                pairs = [f"{k}: {safe_fields.get(k)}" for k in safe_fields.keys()]
                text = "; ".join(pairs)
                if len(text) > max_chars:
                    text = text[: max_chars - 3] + "..."
                return text
            except Exception:
                return "; ".join(f"{k}: {v}" for k, v in list(safe_fields.items())[:6])

    def extract_structured_from_conversation(self, fields_schema: list, conversation_history: list,
                                             max_chars: int = 800) -> Dict[str, Any]:
        """Use Gemini to extract structured fields and a brief summary from conversation.

        Returns: { 'fields': Dict[str, Any], 'summary_text': str, 'confidence': int }
        Fallbacks to a simple heuristic summary when Gemini isn't available.
        """
        # Build schema description
        schema_lines = []
        for f in fields_schema or []:
            name = f.get('name')
            ftype = f.get('type', 'text')
            req = 'required' if f.get('required') else 'optional'
            prompt = f.get('prompt', '')
            schema_lines.append(f"- {name}: type={ftype}, {req}. Prompt: {prompt}")

        # Conversation text
        def fmt_msg(m):
            role = m.get('role', '')
            text = m.get('content') or m.get('text') or ''
            return f"{role.upper()}: {text}".strip()

        convo_text = "\n".join([fmt_msg(m) for m in conversation_history[-30:]])

        # Target JSON shape
        json_instructions = (
            '{\n'
            '  "fields": {"<field_name>": <value or null>, ...},\n'
            '  "summary_text": "<one or two sentences>",\n'
            '  "confidence": <0-100>\n'
            '}'
        )

        # If Gemini not available, fallback
        if not GENAI_AVAILABLE or not getattr(self, 'client', None):
            return {
                'fields': {},
                'summary_text': self.summarize_conversation(conversation_history, max_chars=max_chars),
                'confidence': 0
            }

        prompt = (
            "You are an information extractor. Read the conversation and extract values for the given fields.\n"
            "Return ONLY valid JSON matching the schema exactly.\n\n"
            "Fields Schema:\n" + "\n".join(schema_lines) + "\n\n"
            "Conversation (latest first may be most relevant):\n" + convo_text + "\n\n"
            "Respond as JSON with this exact shape:\n" + json_instructions + "\n"
            "Rules:\n"
            "- For numbers, output numeric types.\n"
            "- For choices, output the chosen option text.\n"
            "- If unknown, set null.\n"
            "- Keep summary_text under two sentences.\n"
        )

        try:
            resp = self.client.models.generate_content(
                model=self.text_model_id,
                contents=prompt
            )
            text = None
            # New SDK returns object with .text sometimes
            if hasattr(resp, 'text') and resp.text:
                text = resp.text
            else:
                # Fallback: try candidates
                cand = getattr(resp, 'candidates', None)
                if cand and len(cand) and hasattr(cand[0], 'content'):
                    parts = getattr(cand[0].content, 'parts', None)
                    if parts and len(parts) and hasattr(parts[0], 'text'):
                        text = parts[0].text
            if not text:
                raise ValueError('Empty Gemini response')

            # Extract JSON
            start = text.find('{')
            end = text.rfind('}') + 1
            data = {}
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                raise ValueError('No JSON found in response')

            fields = data.get('fields') or {}
            summary_text = data.get('summary_text') or self.summarize_conversation(conversation_history, max_chars=max_chars)
            confidence = int(data.get('confidence') or 0)
            return {
                'fields': fields,
                'summary_text': summary_text,
                'confidence': confidence
            }
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            return {
                'fields': {},
                'summary_text': self.summarize_conversation(conversation_history, max_chars=max_chars),
                'confidence': 0
            }
    
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

