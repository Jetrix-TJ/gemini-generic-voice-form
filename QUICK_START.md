# 🚀 QUICK START GUIDE

## What Is This System?

This is a **Form Builder with Voice Support** - like Google Forms, but users can fill forms by talking!

---

## 🎯 5-Minute Setup

### Step 1: Start the Server

```powershell
# In your terminal:
cd C:\Users\harkr\OneDrive\Desktop\techj\voicegen
.\venv\Scripts\activate
python manage.py runserver
```

Server will start at: **http://localhost:8000**

---

### Step 2: Create Your First Form

1. **Open browser**: http://localhost:8000/config/forms/
2. **Click on a template** (e.g., "Contact Form")
3. **Fill in**:
   - Form Name: `My Test Form`
   - Callback URL: Get one from https://webhook.site/
   - (Leave other fields as default)
4. **Click "Create Form"**

---

### Step 3: Get Your Magic Link

After creating the form, you'll see a page with a **Magic Link** like:
```
http://localhost:8000/voice/magic/abc123-def456.../
```

**This is the link you share with users!**

---

### Step 4: Test It

1. Open the magic link in a new tab
2. Click "Start Recording" OR type in text box
3. Fill out the form
4. Check https://webhook.site/ to see the data arrive!

---

## 📁 Page Structure Explained

| URL | Who Uses It | Purpose |
|-----|-------------|---------|
| `/` | Everyone | Landing page |
| `/config/` | **YOU** (Admin) | Dashboard to manage forms |
| `/config/forms/` | **YOU** (Admin) | Create new forms |
| `/voice/magic/xxx/` | **YOUR USERS** | Fill out forms (the link you share) |

---

## 🎤 How Voice Works

When users open your magic link:
1. They click "Start Recording"
2. AI asks questions based on your form
3. Users answer naturally by voice
4. Form gets filled automatically
5. Data sent to your webhook when done

---

## 💡 Real Use Cases

### Example 1: Customer Feedback
- YOU create a "Customer Survey" form at `/config/forms/`
- Get magic link: `http://yoursite.com/voice/magic/abc123/`
- Email this link to customers
- They fill it by voice
- You get data at your webhook

### Example 2: Patient Intake
- Create "Patient Intake" form
- Put magic link on your website
- Patients fill it before appointment
- Data goes to your EHR system webhook

### Example 3: Job Applications
- Create "Job Application" form
- Share link in job posting
- Candidates fill via voice or text
- Applications sent to your HR system

---

## 🔧 Troubleshooting

### "Page Not Found"
- Make sure server is running: `python manage.py runserver`

### "CSRF Error"
- Clear browser cookies
- Use `localhost:8000` (not `127.0.0.1`)

### "WebSocket Error"
- Restart the server
- Check that Django Channels is installed: `pip list | findstr channels`

### "No data at webhook"
- Make sure you entered webhook URL when creating form
- Test webhook at https://webhook.site/ first

---

## 📊 Dashboard Overview

Go to **http://localhost:8000/config/** to see:
- All your forms
- Active sessions (users currently filling forms)
- Completed sessions
- Analytics

---

## ✨ Pro Tips

1. **Test First**: Always test your magic link before sharing
2. **Webhook.site**: Use it to test webhooks before setting up your real endpoint
3. **Expiry Time**: Set link expiry based on use case (24h default)
4. **AI Instructions**: Customize how the AI talks to users in form settings
5. **Multiple Forms**: Create different forms for different purposes!

---

## 🆘 Need Help?

1. Check server logs in terminal
2. Look at browser console (F12)
3. Test with simple "Contact Form" template first
4. Make sure `.env` file has GEMINI_API_KEY set

---

## 🎉 You're Ready!

Now you know:
- ✅ How to create forms (at `/config/forms/`)
- ✅ How to get magic links (after creating form)
- ✅ How users fill forms (via the magic link)
- ✅ How data flows (to your webhook)

Go create your first form! 🚀

