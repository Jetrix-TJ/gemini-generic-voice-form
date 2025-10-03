#!/usr/bin/env python
"""
Simple script to create a sample form configuration
Run this with: python create_sample_form.py
"""

import os

import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voicegen.settings")
django.setup()

from voice_flow.configuration_utils import MagicLinkGenerator
from voice_flow.models import FormConfiguration


def create_sample_form():
    """Create a sample customer survey form"""

    # Create the form configuration
    form_config = FormConfiguration.objects.create(
        name="Customer Survey",
        description="Collect customer feedback through voice interaction",
        ai_instructions="""Be friendly and conversational. Ask about their experience with our service. 
        Use a warm, professional tone. Ask one question at a time and wait for responses.""",
        callback_url="https://webhook.site/your-unique-url-here",  # Replace with your webhook URL
        form_schema={
            "fields": [
                {
                    "name": "customer_name",
                    "type": "text",
                    "required": True,
                    "label": "What's your name?",
                },
                {
                    "name": "satisfaction_rating",
                    "type": "number",
                    "required": True,
                    "label": "How would you rate your experience from 1 to 10?",
                },
                {
                    "name": "feedback",
                    "type": "text",
                    "required": False,
                    "label": "Any additional comments or suggestions?",
                },
            ]
        },
    )

    print(f"✅ Created form: {form_config.name}")
    print(f"   Form ID: {form_config.id}")

    # Generate a magic link
    magic_link = MagicLinkGenerator.generate_magic_link(
        form_config_id=form_config.id, expires_in_hours=24
    )

    print(f"🔗 Magic Link: {magic_link}")
    print(
        f"   Access URL: http://localhost:8000/voice/magic/{magic_link.split('/')[-1]}/"
    )

    return form_config, magic_link


if __name__ == "__main__":
    try:
        form, link = create_sample_form()
        print("\n🎉 Form created successfully!")
        print(
            "You can now test the voice interface using the magic link above."
        )
    except Exception as e:
        print(f"❌ Error creating form: {e}")
