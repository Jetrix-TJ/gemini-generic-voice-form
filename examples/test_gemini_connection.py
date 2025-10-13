#!/usr/bin/env python
"""
Test Google Gemini API connection
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import google.generativeai as genai
except ImportError:
    print("❌ Error: google-generativeai not installed")
    print("Install it with: pip install google-generativeai")
    sys.exit(1)


def test_gemini_connection():
    """Test connection to Google Gemini API"""
    
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in environment variables")
        print("\nPlease set your Gemini API key:")
        print("  export GEMINI_API_KEY='your_api_key_here'")
        print("  or add it to your .env file")
        return False
    
    print(f"🔑 Using API Key: {api_key[:10]}...")
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Create model
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        print("\n✅ Successfully connected to Google Gemini API")
        print("📡 Testing model response...\n")
        
        # Test generation
        response = model.generate_content("Say 'Hello, VoiceGen!' in a friendly way.")
        
        print("🤖 Gemini Response:")
        print("-" * 50)
        print(response.text)
        print("-" * 50)
        
        print("\n✅ Connection test successful!")
        print("You're all set to use VoiceGen with Gemini AI!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error connecting to Gemini API: {e}")
        print("\nPossible solutions:")
        print("1. Verify your API key is correct")
        print("2. Check your internet connection")
        print("3. Ensure you have API quota available")
        print("4. Visit: https://makersuite.google.com/app/apikey")
        return False


if __name__ == '__main__':
    print("=" * 50)
    print("Google Gemini API Connection Test")
    print("=" * 50)
    print()
    
    success = test_gemini_connection()
    sys.exit(0 if success else 1)

