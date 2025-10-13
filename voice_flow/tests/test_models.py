"""
Tests for Voice Flow models
"""
from django.test import TestCase
from datetime import timedelta
from django.utils import timezone
from voice_flow.models import APIKey, VoiceFormConfig, MagicLinkSession


class APIKeyModelTest(TestCase):
    """Test APIKey model"""
    
    def test_create_api_key(self):
        """Test creating an API key"""
        api_key = APIKey.objects.create(name="Test Key")
        
        self.assertIsNotNone(api_key.key)
        self.assertTrue(api_key.key.startswith('vf_'))
        self.assertEqual(api_key.name, "Test Key")
        self.assertTrue(api_key.is_active)
        self.assertIsNone(api_key.last_used_at)
    
    def test_mark_api_key_used(self):
        """Test marking API key as used"""
        api_key = APIKey.objects.create(name="Test Key")
        self.assertIsNone(api_key.last_used_at)
        
        api_key.mark_used()
        self.assertIsNotNone(api_key.last_used_at)


class VoiceFormConfigModelTest(TestCase):
    """Test VoiceFormConfig model"""
    
    def setUp(self):
        self.api_key = APIKey.objects.create(name="Test Key")
    
    def test_create_form_config(self):
        """Test creating a form configuration"""
        form = VoiceFormConfig.objects.create(
            api_key=self.api_key,
            name="Test Form",
            description="Test Description",
            fields=[
                {
                    "name": "test_field",
                    "type": "text",
                    "required": True,
                    "prompt": "Test prompt"
                }
            ],
            ai_prompt="Test AI prompt",
            callback_url="https://example.com/webhook"
        )
        
        self.assertIsNotNone(form.form_id)
        self.assertTrue(form.form_id.startswith('f_'))
        self.assertEqual(form.name, "Test Form")
        self.assertIsNotNone(form.webhook_secret)
        self.assertTrue(form.webhook_secret.startswith('wh_'))
        self.assertTrue(form.is_active)
    
    def test_get_magic_link(self):
        """Test getting magic link URL"""
        form = VoiceFormConfig.objects.create(
            api_key=self.api_key,
            name="Test Form",
            fields=[],
            ai_prompt="Test",
            callback_url="https://example.com/webhook"
        )
        
        magic_link = form.get_magic_link("http://localhost:8000")
        self.assertIn(form.form_id, magic_link)
        self.assertTrue(magic_link.startswith("http://localhost:8000/f/"))


class MagicLinkSessionModelTest(TestCase):
    """Test MagicLinkSession model"""
    
    def setUp(self):
        self.api_key = APIKey.objects.create(name="Test Key")
        self.form = VoiceFormConfig.objects.create(
            api_key=self.api_key,
            name="Test Form",
            fields=[
                {"name": "field1", "type": "text", "required": True, "prompt": "Q1"},
                {"name": "field2", "type": "text", "required": False, "prompt": "Q2"}
            ],
            ai_prompt="Test",
            callback_url="https://example.com/webhook"
        )
    
    def test_create_session(self):
        """Test creating a session"""
        expires_at = timezone.now() + timedelta(hours=24)
        session = MagicLinkSession.objects.create(
            form_config=self.form,
            expires_at=expires_at
        )
        
        self.assertIsNotNone(session.session_id)
        self.assertTrue(session.session_id.startswith('s_'))
        self.assertEqual(session.status, 'pending')
        self.assertEqual(session.fields_completed, 0)
        self.assertFalse(session.webhook_sent)
    
    def test_session_expiry(self):
        """Test session expiry check"""
        # Create expired session
        expired_session = MagicLinkSession.objects.create(
            form_config=self.form,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        self.assertTrue(expired_session.is_expired())
        
        # Create valid session
        valid_session = MagicLinkSession.objects.create(
            form_config=self.form,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.assertFalse(valid_session.is_expired())
    
    def test_mark_session_started(self):
        """Test marking session as started"""
        session = MagicLinkSession.objects.create(
            form_config=self.form,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        self.assertEqual(session.status, 'pending')
        self.assertIsNone(session.started_at)
        
        session.mark_started()
        self.assertEqual(session.status, 'active')
        self.assertIsNotNone(session.started_at)
    
    def test_update_collected_data(self):
        """Test updating collected data"""
        session = MagicLinkSession.objects.create(
            form_config=self.form,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        session.update_collected_data('field1', 'test value')
        self.assertEqual(session.collected_data['field1'], 'test value')
        self.assertEqual(session.fields_completed, 1)
        
        session.update_collected_data('field2', 'another value')
        self.assertEqual(session.fields_completed, 2)
    
    def test_completion_percentage(self):
        """Test completion percentage calculation"""
        session = MagicLinkSession.objects.create(
            form_config=self.form,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        self.assertEqual(session.get_completion_percentage(), 0)
        
        session.update_collected_data('field1', 'value1')
        self.assertEqual(session.get_completion_percentage(), 50)
        
        session.update_collected_data('field2', 'value2')
        self.assertEqual(session.get_completion_percentage(), 100)
    
    def test_add_conversation_message(self):
        """Test adding conversation messages"""
        session = MagicLinkSession.objects.create(
            form_config=self.form,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        session.add_conversation_message('user', 'Hello')
        self.assertEqual(len(session.conversation_history), 1)
        self.assertEqual(session.total_interactions, 1)
        
        session.add_conversation_message('assistant', 'Hi there', 'field1')
        self.assertEqual(len(session.conversation_history), 2)
        self.assertEqual(session.total_interactions, 2)

