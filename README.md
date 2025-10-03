# Voice-Powered Patient Intake System

A Django-based voice-powered patient intake system that uses Google Gemini 2.5 Flash for natural language processing and real-time voice interactions. The system combines WebSocket communication, AI conversation management, and dynamic form completion to streamline hospital patient registration.

## Features

- **Real-time Voice Processing**: Web Audio API integration with Google Gemini 2.5 Flash native audio dialog
- **Dynamic Form Population**: AI-powered form completion with real-time validation
- **WebSocket Communication**: Bidirectional real-time communication between client and server
- **Comprehensive Data Collection**: Patient information, medical history, insurance, and consent forms
- **File Upload Support**: Document and image attachment handling
- **Progress Tracking**: Visual checklist with completion status
- **Responsive Design**: Mobile-friendly interface with Tailwind CSS

## Architecture

### Backend Components
- **Django 5.2.5** with Django REST Framework 3.16.1
- **Django Channels 4.1.0** for WebSocket support (ASGI application)
- **SQLite database** (development) with comprehensive medical data models
- **Google Gemini 2.5 Flash** integration with native audio dialog capabilities

### Frontend Components
- **Vanilla JavaScript** with Web Audio API
- **Tailwind CSS** for responsive design
- **WebSocket client** for real-time communication
- **Dynamic UI updates** based on AI responses

### Data Models
- **Appointment**: Comprehensive patient data structure (5 main sections)
- **AppointmentAttachment**: File upload support for medical documents
- **VoiceSession**: Voice conversation session tracking

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd voicegen

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment file
cp env.example .env

# Edit .env file with your configuration
# At minimum, you need:
# SECRET_KEY=your-secret-key-here
# GEMINI_API_KEY=your-gemini-api-key-here
```

### 3. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 4. Run the Server

```bash
# Development server
python manage.py runserver

# Or with Daphne (ASGI server for WebSocket support)
daphne voicegen.asgi:application
```

### 5. Access the Application

- Home page: http://localhost:8000/
- Voice interface: http://localhost:8000/voice/
- Admin panel: http://localhost:8000/admin/
- API status: http://localhost:8000/api/status/

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SECRET_KEY` | Django secret key | Yes | - |
| `DEBUG` | Debug mode | No | True |
| `GEMINI_API_KEY` | Google Gemini API key | Yes | - |
| `DATABASE_URL` | Database URL (production) | No | SQLite |
| `REDIS_URL` | Redis URL (production) | No | In-memory |

### Google Gemini Setup

1. Get your API key from [Google AI Studio](https://aistudio.google.com/)
2. Add it to your `.env` file:
   ```
   GEMINI_API_KEY=your-api-key-here
   ```

## API Endpoints

### REST API
- `GET /api/appointments/` - List appointments
- `POST /api/appointments/` - Create appointment
- `GET /api/appointments/{id}/` - Get appointment details
- `PATCH /api/appointments/{id}/` - Update appointment
- `POST /api/appointments/{id}/update_field/` - Update specific field
- `POST /api/appointments/{id}/validate_data/` - Validate appointment data
- `POST /api/appointments/{id}/complete/` - Mark appointment as complete
- `GET /api/appointments/{id}/checklist/` - Get checklist status

### File Upload
- `POST /api/attachments/` - Upload file attachment

### Voice Sessions
- `POST /api/sessions/` - Create voice session
- `GET /api/sessions/{id}/` - Get session details

### WebSocket
- `ws://localhost:8000/ws/voice/{session_id}/` - Voice communication endpoint

## Usage

### Starting a Voice Session

1. Navigate to the voice interface
2. Grant microphone permissions when prompted
3. Click "Start Recording" to begin voice interaction
4. Speak naturally - the AI will ask questions and collect information
5. Watch the progress checklist update in real-time

### Text Input Alternative

- Use the text input field for typing responses instead of voice
- Useful for quiet environments or accessibility needs

### File Uploads

- Upload medical documents, insurance cards, or other relevant files
- Supported formats: Images (JPEG, PNG), PDFs, Documents (DOC, DOCX, RTF, TXT)
- Maximum file size: 10MB

## Data Collection Areas

The system collects comprehensive patient information across five main categories:

### 1. Patient Information
- Personal details (name, DOB, gender, SSN)
- Contact information (phone, email, address)
- Emergency contact information

### 2. Visit Context
- Visit type (new patient, follow-up, urgent care, etc.)
- Reason for visit
- Referring physician
- Insurance information

### 3. Medical Information
- Current symptoms
- Medications
- Allergies
- Medical history
- Family history
- Current conditions

### 4. Accessibility
- Preferred language
- Interpreter needs
- Mobility assistance
- Hearing/visual assistance

### 5. Consent & Communication
- Treatment consent
- Billing consent
- Communication preferences
- Record sharing consent

## Development

### Project Structure

```
voicegen/
├── voicegen/              # Main Django project
│   ├── settings.py        # Django settings
│   ├── urls.py           # URL configuration
│   ├── asgi.py           # ASGI configuration
│   └── wsgi.py           # WSGI configuration
├── voice_flow/           # Main application
│   ├── models.py         # Data models
│   ├── views.py          # API views
│   ├── consumers.py      # WebSocket consumers
│   ├── serializers.py    # API serializers
│   ├── utils.py          # Utility functions
│   └── routing.py        # WebSocket routing
├── templates/            # HTML templates
├── static/               # Static files
│   ├── voice-flow-core.js    # Core JavaScript
│   └── voice-flow-ui.js      # UI JavaScript
└── requirements.txt      # Python dependencies
```

### Adding New Fields

1. Update the `Appointment` model in `voice_flow/models.py`
2. Run migrations: `python manage.py makemigrations && python manage.py migrate`
3. Update the checklist in `voice_flow/utils.py`
4. Update the admin interface in `voice_flow/admin.py`

### Customizing AI Behavior

Modify the system instruction in `voice_flow/consumers.py`:

```python
def get_system_instruction(self):
    return """
    Your custom instructions for the AI assistant...
    """
```

## Deployment

### Production Settings

For production deployment, update your `.env` file:

```bash
DEBUG=False
SECRET_KEY=your-production-secret-key
DATABASE_URL=postgresql://user:password@localhost:5432/voicegen
REDIS_URL=redis://localhost:6379/0
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### Docker Deployment (Optional)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["daphne", "voicegen.asgi:application", "--bind", "0.0.0.0", "--port", "8000"]
```

### Environment Requirements

- Python 3.11+
- PostgreSQL (production)
- Redis (production, for WebSocket scaling)
- SSL certificate (production)

## Security Considerations

- All user data is encrypted in transit (HTTPS)
- File uploads are validated for type and size
- Input validation on all form fields
- CSRF protection enabled
- SQL injection protection via Django ORM

## Troubleshooting

### Common Issues

1. **Microphone not working**: Check browser permissions and HTTPS requirement
2. **WebSocket connection failed**: Verify server is running with ASGI support
3. **Gemini API errors**: Check API key and quota limits
4. **File upload errors**: Verify file type and size limits

### Debug Mode

Enable debug mode in `.env`:
```
DEBUG=True
```

Check browser console and Django logs for detailed error information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the API documentation

## Roadmap

- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Integration with EHR systems
- [ ] Mobile app development
- [ ] Advanced AI conversation flows
- [ ] Real-time collaboration features
