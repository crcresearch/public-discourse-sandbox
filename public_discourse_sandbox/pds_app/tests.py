from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from public_discourse_sandbox.pds_app.models import Experiment, UserProfile, Post

User = get_user_model()

"""
docker compose -f docker-compose.local.yml run --rm django python manage.py test pds_app
"""

# Disable MFA middleware for tests
@override_settings(MIDDLEWARE=[
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
])
class BanUserTests(TestCase):
    """
    docker compose -f docker-compose.local.yml run --rm django python manage.py test pds_app.tests.BanUserTests
    """
    def setUp(self):
        # Create test users
        self.moderator = User.objects.create_user(
            email='moderator@example.com',
            password='testpass123',
            name='Moderator'
        )
        self.regular_user = User.objects.create_user(
            email='regular@example.com',
            password='testpass123',
            name='Regular User'
        )
        self.target_user = User.objects.create_user(
            email='target@example.com',
            password='testpass123',
            name='Target User'
        )
        
        # Create test experiment
        self.experiment = Experiment.objects.create(
            name='Test Experiment',
            description='Test Description',
            creator=self.moderator
        )
        
        # Create user profiles
        self.moderator_profile = UserProfile.objects.create(
            user=self.moderator,
            experiment=self.experiment,
            username='moderator',
            display_name='Moderator',
            is_moderator=True
        )
        self.regular_profile = UserProfile.objects.create(
            user=self.regular_user,
            experiment=self.experiment,
            username='regular',
            display_name='Regular User'
        )
        self.target_profile = UserProfile.objects.create(
            user=self.target_user,
            experiment=self.experiment,
            username='target',
            display_name='Target User'
        )
        
        # Set up the test client
        self.client = Client(HTTP_X_REQUESTED_WITH='XMLHttpRequest')  # Make all requests AJAX
        
    def test_ban_user_success(self):
        """
        Test successful ban of a user by a moderator.
        docker compose -f docker-compose.local.yml run --rm django python manage.py test pds_app.tests.BanUserTests.test_ban_user_success
        """
        # Set up the moderator's session
        self.client.force_login(self.moderator)
        self.moderator.last_accessed = self.experiment
        self.moderator.save()
        
        url = reverse('ban_user', kwargs={'user_profile_id': self.target_profile.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        # Refresh target profile from database
        self.target_profile.refresh_from_db()
        self.assertTrue(self.target_profile.is_banned)
        
    def test_ban_user_unauthorized(self):
        """Test ban attempt by non-moderator."""
        # Set up the regular user's session
        self.client.force_login(self.regular_user)
        self.regular_user.last_accessed = self.experiment
        self.regular_user.save()
        
        url = reverse('ban_user', kwargs={'user_profile_id': self.target_profile.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')
        
        # Target profile should not be banned
        self.target_profile.refresh_from_db()
        self.assertFalse(self.target_profile.is_banned)
        
    def test_ban_user_not_logged_in(self):
        """Test ban attempt without authentication."""
        url = reverse('ban_user', kwargs={'user_profile_id': self.target_profile.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Target profile should not be banned
        self.target_profile.refresh_from_db()
        self.assertFalse(self.target_profile.is_banned)
        
    def test_ban_user_invalid_method(self):
        """Test ban attempt with invalid HTTP method."""
        # Set up the moderator's session
        self.client.force_login(self.moderator)
        self.moderator.last_accessed = self.experiment
        self.moderator.save()
        
        url = reverse('ban_user', kwargs={'user_profile_id': self.target_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['status'], 'error')
        
    def test_ban_user_invalid_profile(self):
        """Test ban attempt with invalid user profile ID."""
        # Set up the moderator's session
        self.client.force_login(self.moderator)
        self.moderator.last_accessed = self.experiment
        self.moderator.save()
        
        url = reverse('ban_user', kwargs={'user_profile_id': '00000000-0000-0000-0000-000000000000'})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 404)
        
    def test_ban_user_different_experiment(self):
        """Test ban attempt on user from different experiment."""
        # Create another experiment
        other_experiment = Experiment.objects.create(
            name='Other Experiment',
            description='Other Description',
            creator=self.moderator
        )
        
        # Create a profile in the other experiment
        other_profile = UserProfile.objects.create(
            user=self.target_user,
            experiment=other_experiment,
            username='other_target',
            display_name='Other Target'
        )
        
        # Set up the moderator's session
        self.client.force_login(self.moderator)
        self.moderator.last_accessed = self.experiment  # Set to original experiment
        self.moderator.save()
        
        url = reverse('ban_user', kwargs={'user_profile_id': other_profile.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')
        
        # Profile should not be banned
        other_profile.refresh_from_db()
        self.assertFalse(other_profile.is_banned) 