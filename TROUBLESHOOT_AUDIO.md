# 🔍 Troubleshooting Audio Issues

## Check These Steps

### 1. Refresh the Page
```
http://localhost:8000/f/f_mpURImWhrd7c29b2
```

### 2. Open Browser Console (F12)

Look for:
- "WebSocket connected" ✅
- "Microphone permission granted" ✅
- Any audio errors?

### 3. Check Server Logs

You should see:
```
INFO: Live API connected!
INFO: All audio tasks started - streaming active!
INFO: Ready to send audio to Gemini...
INFO: Starting to receive audio from Gemini...
INFO: Ready to send audio to browser...
```

### 4. Click Microphone and Speak

Check if you see:
```
DEBUG: Received X bytes from browser
DEBUG: Sending audio to Gemini: X bytes
```

### 5. Check if Gemini Responds

Look for:
```
INFO: Gemini says: <text>
DEBUG: Received X bytes of audio from Gemini
DEBUG: Sending X bytes to browser
```

## Common Issues

### Issue: "Can't hear Gemini"

**Possible Causes:**
1. Gemini isn't speaking yet (needs audio input first)
2. Browser audio context not started
3. Audio format mismatch
4. No speakers/headphones

**Solutions:**
1. **Click microphone and SAY SOMETHING** - Gemini responds to your voice
2. **Click anywhere on page** - Activates audio context
3. **Check browser console** - Look for errors
4. **Try headphones** - Make sure they're connected

### Issue: "Microphone not working"

**Check:**
1. Browser permissions granted?
2. Correct microphone selected?
3. Check browser console for errors

**Fix:**
```javascript
// In browser console:
navigator.mediaDevices.getUserMedia({audio: true})
  .then(() => console.log("Mic OK"))
  .catch(err => console.error("Mic error:", err))
```

### Issue: "WebSocket closes immediately"

This was the Redis error - should be FIXED now with in-memory channel layer.

## Test Audio Playback

Open browser console and run:

```javascript
// Test if audio context works
const audioCtx = new AudioContext();
console.log("Audio context state:", audioCtx.state);

// If suspended, click the page
if (audioCtx.state === 'suspended') {
    audioCtx.resume().then(() => console.log("Audio resumed!"));
}
```

## Debug Mode

In your browser, open the link and check console for these messages:

1. "WebSocket connected" - ✅ Good!
2. "Microphone permission granted" - ✅ Good!
3. "Received message: {type: 'ready'...}" - ✅ Good!
4. After clicking mic and speaking:
   - Should see audio being sent
   - Should receive audio back
   - Should play through speakers

## What's Working

Looking at your logs:
- ✅ Gemini Live API connects successfully
- ✅ WebSocket stays alive (keepalive pings working)
- ✅ Audio tasks started
- ✅ No more Redis errors!

## What to Test

1. **Click microphone button** 🎤
2. **Say "Hello"**  
3. **Watch server logs** - Should see:
   ```
   DEBUG: Received X bytes from browser
   DEBUG: Sending audio to Gemini
   INFO: Gemini says: <response text>
   DEBUG: Received X bytes of audio from Gemini
   DEBUG: Sending X bytes to browser
   ```
4. **Listen** - You should hear Gemini!

## The Flow

```
You speak → Browser captures (16kHz PCM) → 
WebSocket binary → Server receives → 
Gemini processes → Gemini speaks → 
Server receives (24kHz PCM) → WebSocket binary → 
Browser plays → You hear! 🔊
```

## Quick Fix

If still no audio:

1. **Restart server** (already done)
2. **Hard refresh page** (Ctrl+Shift+R)
3. **Click mic button**
4. **Speak loudly and clearly**
5. **Wait 1-2 seconds**

Gemini should respond!

---

**Try it now and check the server logs!** 🎙️

