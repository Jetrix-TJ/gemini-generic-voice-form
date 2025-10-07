#!/usr/bin/env python3
"""
Test script to verify Gemini API connection and Live API availability
"""

import os
import asyncio
from dotenv import load_dotenv
import google.generativeai as genai
from google import genai as genai_client
from google.genai import types

# Load environment variables
load_dotenv()

async def test_gemini_connection():
    """Test Gemini API connection and Live API availability"""
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment variables")
        print("💡 Create a .env file with: GEMINI_API_KEY=your-api-key-here")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Test basic API connectivity
    try:
        print("🔍 Testing basic Gemini API connectivity...")
        client = genai_client.Client(api_key=api_key)
        print("✅ Basic client creation successful")
    except Exception as e:
        print(f"❌ Basic client creation failed: {e}")
        return False
    
    # Test regular API
    try:
        print("🔍 Testing regular Gemini API...")
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content("Hello, this is a test.")
        print(f"✅ Regular API test successful: {response.text[:50]}...")
    except Exception as e:
        print(f"❌ Regular API test failed: {e}")
        # Try alternative models
        try:
            print("🔍 Trying alternative model...")
            model = genai.GenerativeModel("gemini-1.5-pro")
            response = model.generate_content("Hello, this is a test.")
            print(f"✅ Regular API test successful with alternative model: {response.text[:50]}...")
        except Exception as e2:
            print(f"❌ Alternative model also failed: {e2}")
            return False
    
    # Test Live API models
    live_models = [
        "models/gemini-2.0-flash-exp",
        "models/gemini-live-2.5-flash-preview", 
        "models/gemini-2.5-flash-native-audio-preview"
    ]
    
    print("🔍 Testing Live API models...")
    live_api_available = False
    
    for model in live_models:
        try:
            print(f"🔄 Trying Live API model: {model}")
            
            # Try to create a Live session to test if the model supports it
            async with client.aio.live.connect(model=model) as session:
                print(f"✅ Model {model} supports Live API")
                live_api_available = True
                break
                
        except Exception as e:
            print(f"⚠️ Model {model} failed: {e}")
            continue
    
    if live_api_available:
        print("✅ Live API appears to be available")
    else:
        print("❌ No Live API models are working")
        print("💡 This might be due to:")
        print("   - API key doesn't have Live API access")
        print("   - Regional restrictions")
        print("   - Model availability issues")
    
    return live_api_available

if __name__ == "__main__":
    print("🧪 Testing Gemini API Connection...")
    asyncio.run(test_gemini_connection())
