#!/usr/bin/env python
"""
Test Gemini Live API with Native Audio
Based on Google's official Live API example

Run this to verify your setup works with Gemini 2.5 Flash Native Audio.

Requirements:
- brew install portaudio (macOS) or apt-get install portaudio19-dev (Linux)
- pip install google-genai pyaudio python-dotenv

Important: **Use headphones** to prevent echo/feedback!
"""

import asyncio
import sys
import traceback
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Check dependencies
try:
    import pyaudio
except ImportError:
    print("❌ Error: pyaudio not installed")
    print("\nInstall with:")
    print("  macOS: brew install portaudio && pip install pyaudio")
    print("  Linux: sudo apt-get install portaudio19-dev && pip install pyaudio")
    print("  Windows: Download wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")
    sys.exit(1)

try:
    from google import genai
except ImportError:
    print("❌ Error: google-genai not installed")
    print("Install with: pip install google-genai")
    sys.exit(1)

if sys.version_info < (3, 11, 0):
    try:
        import taskgroup, exceptiongroup
        asyncio.TaskGroup = taskgroup.TaskGroup
        asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup
    except ImportError:
        print("❌ Error: taskgroup and exceptiongroup required for Python < 3.11")
        print("Install with: pip install taskgroup exceptiongroup")
        sys.exit(1)


# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()


# Gemini configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("❌ Error: GEMINI_API_KEY not set")
    print("Set it with: export GEMINI_API_KEY='your_api_key_here'")
    print("Or add to .env file")
    sys.exit(1)

client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={"api_version": "v1alpha"}
)

system_instruction = """
You are conducting a quick voice form survey. 

Ask the user these questions one at a time:
1. "What is your name?"
2. "How would you rate your experience from 1 to 10?"
3. "Would you recommend us to a friend?"

Be friendly, conversational, and wait for responses before continuing.
After all questions, thank them and end the conversation.
"""

MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"
CONFIG = {
    "system_instruction": system_instruction,
    "response_modalities": ["AUDIO"],
    "proactivity": {'proactive_audio': True}
}


class AudioLoop:
    def __init__(self):
        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.audio_stream = None

    async def listen_audio(self):
        """Listen to microphone and send to Gemini"""
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        
        print(f"🎤 Microphone: {mic_info['name']}")
        print("🎧 Start speaking (use headphones!)")
        
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def send_realtime(self):
        """Send audio from queue to Gemini"""
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def receive_audio(self):
        """Receive audio from Gemini and queue for playback"""
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(f"🤖 Gemini: {text}")

            # Handle interruptions - clear audio queue
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        """Play audio responses from Gemini"""
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        
        print("🔊 Audio output ready")
        
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        """Main event loop"""
        try:
            print("\n" + "="*70)
            print("🎙️  Gemini Live API Test - Voice Form Demo")
            print("="*70)
            print(f"\n✅ API Key: {GEMINI_API_KEY[:20]}...")
            print(f"✅ Model: {MODEL}")
            print(f"✅ Audio: {SEND_SAMPLE_RATE}Hz input, {RECEIVE_SAMPLE_RATE}Hz output")
            print("\n⚠️  IMPORTANT: Use headphones to prevent echo!")
            print("\nConnecting to Gemini Live API...")
            
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session
                print("✅ Connected to Gemini!\n")
                
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                # Start all tasks
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())
                
        except asyncio.CancelledError:
            print("\n\n👋 Session ended")
        except asyncio.ExceptionGroup as eg:
            if self.audio_stream:
                self.audio_stream.close()
            print(f"\n❌ Error occurred:")
            traceback.print_exception(eg)
        except Exception as e:
            if self.audio_stream:
                self.audio_stream.close()
            print(f"\n❌ Error: {e}")
            traceback.print_exc()


def check_audio_devices():
    """Check available audio devices"""
    print("\n📋 Available Audio Devices:")
    print("-" * 70)
    
    for i in range(pya.get_device_count()):
        info = pya.get_device_info_by_index(i)
        print(f"  [{i}] {info['name']}")
        print(f"      Input channels: {info['maxInputChannels']}")
        print(f"      Output channels: {info['maxOutputChannels']}")
        print(f"      Default sample rate: {info['defaultSampleRate']}")
        print()
    
    default_input = pya.get_default_input_device_info()
    default_output = pya.get_default_output_device_info()
    
    print(f"🎤 Default Input: {default_input['name']}")
    print(f"🔊 Default Output: {default_output['name']}")
    print()


if __name__ == "__main__":
    print("\n" + "="*70)
    print("VoiceGen - Gemini Live API Test")
    print("="*70)
    
    # Check audio devices
    check_audio_devices()
    
    # Run test
    loop = AudioLoop()
    
    try:
        asyncio.run(loop.run())
    except KeyboardInterrupt:
        print("\n\n👋 Stopped by user")
        sys.exit(0)

