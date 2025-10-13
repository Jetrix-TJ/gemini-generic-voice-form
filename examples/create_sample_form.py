#!/usr/bin/env python
"""
Example script to create a sample voice form using the Python SDK
"""
import os
import sys

# Add parent directory to path to import SDK
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))

from voiceforms import VoiceFormSDK
from voiceforms.client import (
    create_text_field,
    create_number_field,
    create_choice_field,
    create_email_field,
    create_boolean_field
)


def create_customer_feedback_form(api_key: str, base_url: str = 'http://localhost:8000'):
    """Create a comprehensive customer feedback form"""
    
    sdk = VoiceFormSDK(api_key=api_key, base_url=base_url)
    
    form_config = {
        'name': 'Customer Feedback Survey',
        'description': 'Collect detailed customer feedback through natural voice conversation',
        'fields': [
            create_text_field(
                'customer_name',
                'What is your full name?',
                required=True,
                min_length=2,
                max_length=100
            ),
            create_email_field(
                'email',
                'What is your email address?',
                required=False
            ),
            create_choice_field(
                'product_purchased',
                'Which product did you purchase?',
                options=['Product A', 'Product B', 'Product C', 'Other'],
                required=True
            ),
            create_number_field(
                'satisfaction_rating',
                'On a scale of 1 to 10, how satisfied are you with your purchase?',
                required=True,
                min_value=1,
                max_value=10,
                integer_only=True
            ),
            create_boolean_field(
                'would_recommend',
                'Would you recommend our product to a friend?',
                required=True
            ),
            create_text_field(
                'feedback_comments',
                'Please share any additional feedback or suggestions you have',
                required=False,
                max_length=500
            )
        ],
        'ai_prompt': '''
        Hello! Thank you for taking the time to share your feedback with us. 
        I'm an AI assistant and I'll guide you through a short survey about your recent purchase. 
        This should only take a few minutes. Let's get started!
        ''',
        'callback_url': 'https://webhook.site/unique-id-here',  # Replace with your webhook URL
        'callback_method': 'POST',
        'success_message': 'Thank you so much for your valuable feedback! We really appreciate you taking the time to help us improve.',
        'settings': {
            'max_duration_minutes': 10,
            'language': 'en-US',
            'voice_style': 'friendly',
            'allow_interruptions': True
        }
    }
    
    print("Creating customer feedback form...")
    result = sdk.create_form(form_config)
    
    print("\n✅ Form Created Successfully!")
    print(f"Form ID: {result['form_id']}")
    print(f"Magic Link: {result['magic_link']}")
    print(f"Webhook Secret: {result['webhook_secret']}")
    print(f"Created At: {result['created_at']}")
    
    # Generate a test session
    print("\nGenerating test session link...")
    session = sdk.generate_session_link(
        form_id=result['form_id'],
        session_data={
            'source': 'example_script',
            'test': True,
            'created_by': 'developer'
        },
        expires_in_hours=24
    )
    
    print("\n✅ Session Created!")
    print(f"Session ID: {session['session_id']}")
    print(f"Session Link: {session['magic_link']}")
    print(f"Expires At: {session['expires_at']}")
    
    print("\n🎯 Next Steps:")
    print("1. Open the session link in your browser")
    print("2. Complete the form using voice or text")
    print("3. Check your webhook URL for the submitted data")
    
    return result, session


def create_lead_qualification_form(api_key: str, base_url: str = 'http://localhost:8000'):
    """Create a lead qualification form for sales"""
    
    sdk = VoiceFormSDK(api_key=api_key, base_url=base_url)
    
    form_config = {
        'name': 'Lead Qualification Form',
        'description': 'Qualify sales leads through conversational AI',
        'fields': [
            create_text_field(
                'company_name',
                'What is the name of your company?',
                required=True
            ),
            create_text_field(
                'contact_name',
                'And your name?',
                required=True
            ),
            create_email_field(
                'email',
                'What is your work email?',
                required=True
            ),
            create_choice_field(
                'company_size',
                'How many employees does your company have?',
                options=['1-10', '11-50', '51-200', '201-500', '500+'],
                required=True
            ),
            create_choice_field(
                'budget_range',
                'What is your budget range for this project?',
                options=['Under $10k', '$10k-$50k', '$50k-$100k', 'Over $100k'],
                required=True
            ),
            create_choice_field(
                'timeline',
                'When are you looking to get started?',
                options=['Immediately', 'Within 1 month', 'Within 3 months', 'Just exploring'],
                required=True
            ),
            create_text_field(
                'requirements',
                'Can you briefly describe what you are looking for?',
                required=False
            )
        ],
        'ai_prompt': '''
        Hi! Thanks for your interest in our services. 
        I'd love to learn more about your needs so we can see how we can help. 
        This will just take a couple of minutes. Ready to start?
        ''',
        'callback_url': 'https://your-crm.com/webhook/leads',
        'success_message': 'Perfect! Thank you for sharing that information. Someone from our team will reach out to you within 24 hours.',
        'settings': {
            'max_duration_minutes': 15,
            'language': 'en-US',
            'voice_style': 'professional',
            'allow_interruptions': True
        }
    }
    
    print("Creating lead qualification form...")
    result = sdk.create_form(form_config)
    
    print("\n✅ Form Created Successfully!")
    print(f"Form ID: {result['form_id']}")
    print(f"Magic Link: {result['magic_link']}")
    
    return result


def create_event_registration_form(api_key: str, base_url: str = 'http://localhost:8000'):
    """Create an event registration form"""
    
    sdk = VoiceFormSDK(api_key=api_key, base_url=base_url)
    
    form_config = {
        'name': 'Event Registration',
        'description': 'Register attendees for events via voice',
        'fields': [
            create_text_field('name', 'What is your full name?', required=True),
            create_email_field('email', 'What email should we send the confirmation to?', required=True),
            create_choice_field(
                'ticket_type',
                'Which ticket type would you like?',
                options=['General Admission', 'VIP', 'Student'],
                required=True
            ),
            create_text_field(
                'dietary_restrictions',
                'Do you have any dietary restrictions we should know about?',
                required=False
            ),
            create_boolean_field(
                'needs_accommodation',
                'Will you need any special accommodations?',
                required=False
            )
        ],
        'ai_prompt': 'Welcome! Let me help you register for our upcoming event.',
        'callback_url': 'https://your-event-system.com/webhook/registrations',
        'success_message': 'You are all registered! Check your email for confirmation details.'
    }
    
    print("Creating event registration form...")
    result = sdk.create_form(form_config)
    
    print("\n✅ Form Created Successfully!")
    print(f"Form ID: {result['form_id']}")
    print(f"Magic Link: {result['magic_link']}")
    
    return result


if __name__ == '__main__':
    # Get API key from environment or command line
    api_key = os.getenv('VOICEGEN_API_KEY')
    
    if not api_key and len(sys.argv) > 1:
        api_key = sys.argv[1]
    
    if not api_key:
        print("❌ Error: API key not provided")
        print("\nUsage:")
        print("  python create_sample_form.py YOUR_API_KEY")
        print("  or set VOICEGEN_API_KEY environment variable")
        sys.exit(1)
    
    base_url = os.getenv('VOICEGEN_BASE_URL', 'http://localhost:8000')
    
    print("=== VoiceGen Form Examples ===\n")
    print(f"Using API Key: {api_key[:10]}...")
    print(f"Base URL: {base_url}\n")
    
    # Create sample forms
    print("\n" + "="*50)
    print("1. Customer Feedback Form")
    print("="*50)
    create_customer_feedback_form(api_key, base_url)
    
    print("\n\n" + "="*50)
    print("2. Lead Qualification Form")
    print("="*50)
    create_lead_qualification_form(api_key, base_url)
    
    print("\n\n" + "="*50)
    print("3. Event Registration Form")
    print("="*50)
    create_event_registration_form(api_key, base_url)
    
    print("\n\n✨ All sample forms created successfully!")

