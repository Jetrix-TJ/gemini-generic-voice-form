"""
Test to verify server_content text extraction from Gemini responses
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voicegen.settings')
django.setup()

from voice_flow.models import MagicLinkSession

# Check the most recent session
sessions = MagicLinkSession.objects.filter(status='completed').order_by('-completed_at')[:5]

print("\n" + "="*70)
print("CHECKING RECENT SESSIONS FOR DATA")
print("="*70 + "\n")

for session in sessions:
    print(f"Session: {session.session_id}")
    print(f"Status: {session.status}")
    print(f"Completed: {session.completed_at}")
    print(f"Conversation history length: {len(session.conversation_history) if session.conversation_history else 0}")
    print(f"Collected data keys: {list(session.collected_data.keys()) if session.collected_data else []}")
    
    if session.conversation_history:
        print("\nConversation:")
        for msg in session.conversation_history:
            print(f"  - {msg}")
    else:
        print("\n⚠️ NO CONVERSATION DATA SAVED")
    
    print("\n" + "-"*70 + "\n")

print("\n💡 If all sessions show empty, the text extraction from server_content needs debugging.")
print("   Check server logs for 'Gemini says:' messages.\n")

