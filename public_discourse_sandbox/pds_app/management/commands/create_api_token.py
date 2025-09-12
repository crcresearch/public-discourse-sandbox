from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from rest_framework.authtoken.models import Token

User = get_user_model()


class Command(BaseCommand):
    help = "create an api token for a user to access external API endpoints"

    def add_arguments(self, parser):
        parser.add_argument(
            "email",
            type=str,
            help="email address of the user to create token for",
        )
        parser.add_argument(
            "--regenerate",
            action="store_true",
            help="regenerate token if it already exists",
        )

    def handle(self, *args, **options):
        email = options["email"]
        regenerate = options["regenerate"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            output = f'user with email "{email}" does not exist'
            raise CommandError(output)

        token, created = Token.objects.get_or_create(user=user)

        if not created and not regenerate:
            self.stdout.write(
                self.style.WARNING(
                    f"Token already exists for user {user.email}. "
                    f"Use --regenerate to create a new token.",
                )
            )
            self.stdout.write(f"existing token: {token.key}")
            return

        if not created and regenerate:
            token.delete()
            token = Token.objects.create(user=user)
            self.stdout.write(
                self.style.SUCCESS(f"regenerated token for user {user.email}"),
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"created new token for user {user.email}"),
            )

        self.stdout.write(f"token: {token.key}")
        self.stdout.write(
            self.style.SUCCESS(
                "Use this token in the Authorization header: "
                "Authorization: Token <token>",
            ),
        )
