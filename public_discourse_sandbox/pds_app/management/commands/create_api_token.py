"""
Management command to create API tokens for users.
Similar to how X API provides tokens for external access.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

User = get_user_model()


class Command(BaseCommand):
    help = 'Create an API token for a user to access external API endpoints'

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            type=str,
            help='Email address of the user to create token for'
        )
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Regenerate token if it already exists'
        )

    def handle(self, *args, **options):
        email = options['email']
        regenerate = options['regenerate']

        try:
            # Get user by email
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{email}" does not exist')

        # Check if token already exists
        token, created = Token.objects.get_or_create(user=user)

        if not created and not regenerate:
            self.stdout.write(
                self.style.WARNING(
                    f'Token already exists for user {user.email}. '
                    f'Use --regenerate to create a new token.'
                )
            )
            self.stdout.write(f'Existing token: {token.key}')
            return

        if not created and regenerate:
            # Delete existing token and create new one
            token.delete()
            token = Token.objects.create(user=user)
            self.stdout.write(
                self.style.SUCCESS(f'Regenerated token for user {user.email}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Created new token for user {user.email}')
            )

        self.stdout.write(f'Token: {token.key}')
        self.stdout.write(
            self.style.SUCCESS(
                'Use this token in the Authorization header: '
                'Authorization: Token <token>'
            )
        )