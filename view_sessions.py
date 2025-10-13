#!/usr/bin/env python
"""
Quick script to view completed survey sessions
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voicegen.settings')
django.setup()

from voice_flow.models import MagicLinkSession
import json

# Get all completed sessions
sessions = MagicLinkSession.objects.filter(status='completed').order_by('-completed_at')

print(f"\n{'='*70}")
print(f"COMPLETED SURVEYS ({sessions.count()} total)")
print(f"{'='*70}\n")

for session in sessions[:10]:  # Show last 10
    print(f"Session: {session.session_id}")
    print(f"Form: {session.form_config.name}")
    print(f"Completed: {session.completed_at}")
    print(f"\nConversation History:")
    print(json.dumps(session.conversation_history, indent=2))
    print(f"\nCollected Data:")
    print(json.dumps(session.collected_data, indent=2))
    print(f"\n{'-'*70}\n")

print(f"Total completed: {sessions.count()}")

