from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from public_discourse_sandbox.pds_app.models import Experiment, UserProfile, Post
from django.core.exceptions import PermissionDenied

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
class PostCreationTests(TestCase):
    """Test cases for post creation functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create experiment first
        self.experiment = Experiment.objects.create(
            name='Test Experiment',
            description='Test Description'
        )

        # Create test users
        self.test_user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.test_user.last_accessed = self.experiment
        self.test_user.save()

        self.banned_user = User.objects.create_user(
            email='banned@example.com',
            password='testpass123'
        )
        self.banned_user.last_accessed = self.experiment
        self.banned_user.save()

        # Create user profiles
        self.test_profile = UserProfile.objects.create(
            user=self.test_user,
            experiment=self.experiment,
            display_name='Test User',
            username='testuser'
        )
        self.banned_profile = UserProfile.objects.create(
            user=self.banned_user,
            experiment=self.experiment,
            is_banned=True,
            display_name='Banned User',
            username='banneduser'
        )

        # Set up test client with AJAX headers
        self.client = Client(HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
    def test_create_post_success(self):
        """
        docker compose -f docker-compose.local.yml run --rm django python manage.py test pds_app.tests.PostCreationTests.test_create_post_success
        """
        # Use force_login to bypass allauth's authentication flow
        self.client.force_login(self.test_user)
        
        # Set the user's last_accessed experiment
        self.test_user.last_accessed = self.experiment
        self.test_user.save()
        
        # First get the page to get the CSRF token and set up the experiment context
        response = self.client.get(
            reverse('home_with_experiment', kwargs={'experiment_identifier': self.experiment.identifier})
        )
        self.assertEqual(response.status_code, 200)
        
        # Get the CSRF token from the response
        csrf_token = response.cookies.get('csrftoken')
        self.assertIsNotNone(csrf_token, "CSRF token not found in response")
        
        # Now make the POST request with the CSRF token and experiment identifier
        response = self.client.post(
            reverse('home_with_experiment', kwargs={'experiment_identifier': self.experiment.identifier}),
            {
                'content': 'Test post content',
                'csrfmiddlewaretoken': csrf_token.value
            },
            follow=True  # Follow the redirect after successful post creation
        )
        
        # The view redirects after successful post creation, so we should get a 200 after following
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Post.objects.filter(content='Test post content').exists())
        
        # Verify the post was created with correct attributes
        post = Post.objects.get(content='Test post content')
        self.assertEqual(post.user_profile, self.test_profile)
        self.assertEqual(post.experiment, self.experiment)
        self.assertEqual(post.depth, 0)
        self.assertIsNone(post.parent_post)
        
        # Verify we were redirected to the correct URL
        self.assertEqual(response.request['PATH_INFO'], reverse('home_with_experiment', kwargs={'experiment_identifier': self.experiment.identifier}))

    def test_create_post_invalid_form(self):
        """
        docker compose -f docker-compose.local.yml run --rm django python manage.py test pds_app.tests.PostCreationTests.test_create_post_invalid_form
        """
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(
            reverse('home_with_experiment', kwargs={'experiment_identifier': self.experiment.identifier}),
            {'content': ''},  # Empty content should be invalid
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(content='').exists())

    def test_create_post_banned_user(self):
        """
        docker compose -f docker-compose.local.yml run --rm django python manage.py test pds_app.tests.PostCreationTests.test_create_post_banned_user
        """
        self.client.login(email='banned@example.com', password='testpass123')
        response = self.client.post(
            reverse('home_with_experiment', kwargs={'experiment_identifier': self.experiment.identifier}),
            {'content': 'Test post content'},
            follow=True
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')
        self.assertEqual(response.json()['message'], 'Your account has been suspended. You cannot perform this action at this time.')
        self.assertFalse(Post.objects.filter(content='Test post content').exists())

    def test_create_post_unauthenticated(self):
        """
        docker compose -f docker-compose.local.yml run --rm django python manage.py test pds_app.tests.PostCreationTests.test_create_post_unauthenticated
        """
        # Create a new client without AJAX headers for this test
        non_ajax_client = Client()
        response = non_ajax_client.post(
            reverse('home_with_experiment', kwargs={'experiment_identifier': self.experiment.identifier}),
            {'content': 'Test post content'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)  # Should redirect to login page
        self.assertRedirects(response, f"{reverse('account_login')}?next={reverse('home_with_experiment', kwargs={'experiment_identifier': self.experiment.identifier})}")
        self.assertFalse(Post.objects.filter(content='Test post content').exists())

    def test_create_post_no_profile(self):
        """
        Test that a user without a profile cannot create a post.
        """
        # Create a user without a profile
        no_profile_user = User.objects.create_user(
            email='noprofile@example.com',
            password='testpass123'
        )
        no_profile_user.last_accessed = self.experiment
        no_profile_user.save()

        # Force login the user
        self.client.force_login(no_profile_user)

        # Try to create a post
        response = self.client.post(
            reverse('home_with_experiment', kwargs={'experiment_identifier': self.experiment.identifier}),
            {'content': 'Test post content'}
        )

        # Should get a 403 response
        self.assertEqual(response.status_code, 403)
        self.assertIn("You do not have a profile in this experiment", str(response.content))

        # No post should be created
        self.assertFalse(Post.objects.filter(content='Test post content').exists()) 