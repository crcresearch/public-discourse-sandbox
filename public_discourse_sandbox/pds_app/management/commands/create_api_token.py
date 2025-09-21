from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from public_discourse_sandbox.pds_app.models import MultiToken

User = get_user_model()


class Command(BaseCommand):
    help = "create an api token for a user to access external API endpoints"

    def add_arguments(self, parser):
        parser.add_argument(
            "email",
            type=str,
            help="email address of the user to create token for",
        )

    def handle(self, *args, **options):
        email = options["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            output = f'user with email "{email}" does not exist'
            raise CommandError(output)

        token = MultiToken.objects.create(user=user)

        self.stdout.write(f"token: {token.key}")
        self.stdout.write(
            self.style.SUCCESS(
                "Use this token in the Authorization header: "
                "Authorization: Bearer <token>",
            ),
        )
