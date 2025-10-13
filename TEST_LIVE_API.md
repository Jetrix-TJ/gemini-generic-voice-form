# 🧪 Test Gemini 2.5 Flash Live API - Quick Guide

## ✅ Server is Running!

Your VoiceGen server is now running with **Full Live API bidirectional audio support**!

---

## 🎯 Quick Test (3 Minutes)

### Step 1: Your Existing Form

You already have a form! Use this link:

```
http://localhost:8000/f/f_mpURImWhrd7c29b2
```

### Step 2: Open in Browser

1. **Put on headphones first!** 🎧 (Important!)
2. Open the link in Chrome or Edge
3. Allow microphone access when prompted

### Step 3: What You'll See

- A beautiful voice interface
- "Live API" badge at the top
- Technical audio specs shown
- Microphone button

### Step 4: Start Conversation

1. **Click the microphone button** 🎤
2. **Start speaking** - Say your name
3. **AI will respond with AUDIO** (you'll hear it!)
4. **Continue the conversation** naturally
5. AI will ask all form questions
6. Your answers are collected automatically

###  Step 5: See the Magic!

- **Latency:** 300-800ms (super fast!)
- **Natural conversation:** Talk like a human
- **Interruptions work:** You can cut in anytime
- **Audio responses:** Hear AI speaking
- **No typing needed:** Pure voice!

---

## 🔑 Your API Key (for creating more forms)

```
vf_ItJeay32VNwIv9Te-KO2J5sHa2H2pqpIg8dil4n6foI
```

---

## 📝 Create New Forms

### Quick Command:

```powershell
.\create-form.ps1
```

### Or Custom Form:

```powershell
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/forms/" -Method POST -Headers @{
    "X-API-Key" = "vf_ItJeay32VNwIv9Te-KO2J5sHa2H2pqpIg8dil4n6foI"
    "Content-Type" = "application/json"
} -Body (@{
    name = "Voice Survey"
    fields = @(
        @{
            name = "satisfaction"
            type = "number"
            required = $true
            prompt = "Rate your satisfaction from 1 to 10"
            validation = @{ min = 1; max = 10 }
        }
    )
    ai_prompt = "Hi! One quick question."
    callback_url = "https://webhook.site/test"
} | ConvertTo-Json -Depth 10)

Write-Host "Magic Link: $($response.magic_link)"
```

---

## 🎤 What to Expect

### When You Open the Link:

1. **Page loads** → Shows "Initializing Live API..."
2. **Connects to Gemini** → "Connected to Live API" (green)
3. **Ready** → "Live API connected. Start speaking!"
4. **Click mic** → Recording indicator appears
5. **Speak** → Your audio streams to Gemini
6. **AI responds** → You HEAR the audio response!
7. **Continue** → Natural back-and-forth conversation
8. **Complete** → "Form completed!" modal appears

---

## 🎧 Why Headphones?

Without headphones:
- AI hears its own voice through your speakers
- Creates echo/feedback loop
- AI gets confused and may interrupt itself

With headphones:
- Clean audio input
- No echo
- Natural conversation
- AI responds appropriately

---

## 📊 Monitor Progress

The interface shows:
- **Progress bar** - How many fields completed
- **Live transcript** - What AI is saying (text version)
- **Connection status** - Green = connected
- **Technical specs** - Audio configuration

---

## 🔍 Check Server Logs

Look at your server terminal to see:
```
INFO: Live API session started for s_xyz123
DEBUG: Gemini text: Hello! What is your name?
INFO: Audio streaming active
```

---

## 🎉 Success Indicators

You'll know it's working when:
- ✅ You hear AI's voice (not synthesized, actual Gemini audio!)
- ✅ Responses are super fast (~500ms)
- ✅ You can interrupt AI naturally
- ✅ Conversation flows smoothly
- ✅ Form completes and shows success

---

## 🐛 If Something Goes Wrong

### No Audio Playing

1. Check browser audio permissions
2. Check headphones/speakers connected
3. Try clicking page (activates audio context)
4. Check browser console for errors

### Can't Connect

1. Server running? Check http://localhost:8000/health/
2. WebSocket blocked? Check firewall
3. Wrong URL? Use exact magic link

### AI Not Responding

1. Check .env has GEMINI_API_KEY
2. Verify API key is valid
3. Check Gemini API quota
4. Look at server logs for errors

---

## 🚀 You're Ready!

**Everything is set up** for full bidirectional audio with Gemini 2.5 Flash Live API!

1. ✅ Server running
2. ✅ Live API configured
3. ✅ Form created
4. ✅ Magic link ready

**Just open the link, put on headphones, and start talking!** 🎙️

---

**Magic Link:** http://localhost:8000/f/f_mpURImWhrd7c29b2

**Go try it now!** 🎉

