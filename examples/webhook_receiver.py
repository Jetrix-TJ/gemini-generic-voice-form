#!/usr/bin/env python
"""
Simple webhook receiver for testing VoiceGen webhooks
Run this to receive and verify webhook payloads locally
"""
from flask import Flask, request, jsonify
import hmac
import hashlib
import json
from datetime import datetime

app = Flask(__name__)

# Store received webhooks in memory (for demo purposes)
received_webhooks = []


@app.route('/webhook/voicegen', methods=['POST'])
def receive_webhook():
    """
    Receive and process VoiceGen webhook
    """
    # Get request data
    payload = request.json
    signature = request.headers.get('X-VoiceForm-Signature', '')
    session_id = request.headers.get('X-VoiceForm-Session-ID', '')
    
    print("\n" + "=" * 70)
    print(f"📨 Webhook Received at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Verify signature (if webhook secret is provided)
    webhook_secret = None  # Set this to your webhook_secret to enable verification
    
    if webhook_secret:
        if verify_signature(payload, signature, webhook_secret):
            print("✅ Signature verified")
        else:
            print("❌ Invalid signature!")
            return jsonify({'error': 'Invalid signature'}), 403
    else:
        print("⚠️  Signature verification skipped (no webhook_secret configured)")
    
    # Display webhook details
    print(f"\n📋 Session ID: {session_id}")
    print(f"📋 Form ID: {payload.get('form_id')}")
    print(f"📋 Completed At: {payload.get('completed_at')}")
    
    # Display collected data
    print("\n📊 Collected Data:")
    print("-" * 70)
    data = payload.get('data', {})
    for key, value in data.items():
        print(f"  {key}: {value}")
    
    # Display metadata
    print("\n📈 Metadata:")
    print("-" * 70)
    metadata = payload.get('metadata', {})
    print(f"  Duration: {metadata.get('duration_seconds')} seconds")
    print(f"  Completion: {metadata.get('completion_percentage')}%")
    print(f"  Fields Completed: {metadata.get('fields_completed')}/{metadata.get('total_fields')}")
    
    if 'session_data' in metadata:
        print(f"  Session Data: {metadata.get('session_data')}")
    
    # Display conversation metrics
    if 'conversation_metrics' in metadata:
        metrics = metadata['conversation_metrics']
        print(f"\n💬 Conversation Metrics:")
        print(f"  Total Interactions: {metrics.get('total_interactions')}")
        print(f"  Retry Count: {metrics.get('retry_count')}")
    
    print("\n" + "=" * 70)
    
    # Store webhook
    received_webhooks.append({
        'timestamp': datetime.now().isoformat(),
        'session_id': session_id,
        'payload': payload
    })
    
    # Return success response
    return jsonify({
        'status': 'success',
        'message': 'Webhook received and processed',
        'session_id': session_id
    }), 200


@app.route('/webhooks', methods=['GET'])
def list_webhooks():
    """List all received webhooks"""
    return jsonify({
        'count': len(received_webhooks),
        'webhooks': received_webhooks
    })


@app.route('/webhooks/clear', methods=['POST'])
def clear_webhooks():
    """Clear all received webhooks"""
    received_webhooks.clear()
    return jsonify({'message': 'Webhooks cleared'})


@app.route('/', methods=['GET'])
def index():
    """Home page"""
    return f"""
    <html>
    <head>
        <title>VoiceGen Webhook Receiver</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #4F46E5; }}
            .info {{ background: #EEF2FF; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            code {{ background: #1F2937; color: #10B981; padding: 2px 8px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h1>🎯 VoiceGen Webhook Receiver</h1>
        <div class="info">
            <h2>Status: Running ✅</h2>
            <p>Webhooks received: <strong>{len(received_webhooks)}</strong></p>
            <p>Webhook endpoint: <code>http://localhost:5000/webhook/voicegen</code></p>
        </div>
        
        <h2>How to Use</h2>
        <ol>
            <li>Use this URL as your <code>callback_url</code> when creating forms:
                <br><code>http://localhost:5000/webhook/voicegen</code>
            </li>
            <li>Complete a voice form</li>
            <li>Check the terminal to see the webhook payload</li>
            <li>Visit <code>/webhooks</code> to see all received webhooks</li>
        </ol>
        
        <h2>Endpoints</h2>
        <ul>
            <li><code>POST /webhook/voicegen</code> - Receive webhooks</li>
            <li><code>GET /webhooks</code> - List all received webhooks</li>
            <li><code>POST /webhooks/clear</code> - Clear webhook history</li>
        </ul>
    </body>
    </html>
    """


def verify_signature(payload: dict, signature: str, webhook_secret: str) -> bool:
    """
    Verify webhook signature
    
    Args:
        payload: The webhook payload
        signature: The signature from X-VoiceForm-Signature header
        webhook_secret: Your webhook secret
    
    Returns:
        True if signature is valid
    """
    payload_str = json.dumps(payload, sort_keys=True)
    expected_signature = hmac.new(
        webhook_secret.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return f"sha256={expected_signature}" == signature


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 Starting VoiceGen Webhook Receiver")
    print("=" * 70)
    print("\n📍 Webhook URL: http://localhost:5000/webhook/voicegen")
    print("📍 Admin URL: http://localhost:5000/")
    print("\nPress Ctrl+C to stop\n")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n\n👋 Webhook receiver stopped")

