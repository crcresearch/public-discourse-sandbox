import os
import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from public_discourse_sandbox.pds_app.models import DigitalTwin
from public_discourse_sandbox.pds_app.models import Experiment
from public_discourse_sandbox.pds_app.models import UserProfile

User = get_user_model()

class Command(BaseCommand):
    """
    docker compose -f docker-compose.local.yml run --rm django python manage.py setup_digital_twins
    """
    help = "Sets up the bots for the application using persona files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing digital twins before creating new ones",
        )

    def handle(self, *args, **options):
        # Get the directory where this script lives
        current_dir = os.path.dirname(os.path.abspath(__file__))
        personas_dir = os.path.join(current_dir, "personas")
        experiment = Experiment.objects.get(name="Public")
        self.stdout.write(f"Looking for personas in: {personas_dir}")

        # Define bot configurations
        bot_configs = {
            "1": {
                "username": "DadBot",
                "display_name": "DadBot",
                "email": "dadbot@example.com",
            },
            "2": {
                "username": "CivicBot",
                "display_name": "CivicBot",
                "email": "civicbot@example.com",
            },
            "3": {
                "username": "Journabot",
                "display_name": "Journabot",
                "email": "journabot@example.com",
            },
        }

        # Get all numbered persona files
        persona_files = []
        for i in range(1, 11):  # 1.txt through 10.txt
            file_path = os.path.join(personas_dir, f"{i}.txt")
            if os.path.exists(file_path):
                persona_files.append(file_path)
                self.stdout.write(f"Found persona file: {file_path}")

        # Get all numbered persona files
        persona_files = []
        for i in range(1, 11):  # 1.txt through 10.txt
            file_path = os.path.join(personas_dir, f"{i}.txt")
            if os.path.exists(file_path):
                persona_files.append(file_path)
                self.stdout.write(f"Found persona file: {file_path}")

        # Delete existing digital twins only if --reset flag is provided
        if options["reset"]:
            DigitalTwin.objects.all().delete()
            self.stdout.write("Deleted existing digital twins")

        # Randomly select 5 persona files to be active
        active_files = random.sample(persona_files, min(5, len(persona_files)))
        self.stdout.write(f"Selected {len(active_files)} digital twins to be active")

        for file_path in persona_files:
            try:
                # Read persona file
                with open(file_path) as f:
                    persona_description = f.read().strip()

                # Get bot number from filename
                bot_number = os.path.splitext(os.path.basename(file_path))[0]

                # Get bot configuration
                bot_config = bot_configs.get(bot_number, {
                    "username": f"bot{bot_number}",
                    "display_name": f"Bot {bot_number}",
                    "email": f"bot{bot_number}@example.com",
                })

                # Create or get user
                user, created = User.objects.get_or_create(
                    name=bot_config["username"],
                    defaults={
                        "email": bot_config["email"],
                        "is_active": True,
                    },
                )

                if created:
                    user.set_password("botpassword123")
                    user.save()
                    self.stdout.write(f"Created user for {bot_config['display_name']}")

                # Create or update bot profile
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "is_digital_twin": True,
                        "username": bot_config["username"],
                        "display_name": bot_config["display_name"],
                        # 'visibility': 'public'
                        "is_private": True,
                        "is_deleted": False,
                        "experiment": experiment,
                    },
                )

                if not created:
                    profile.full_name = bot_config["display_name"]
                    profile.save()

                if created:
                    self.stdout.write(f"Created profile for {bot_config['display_name']}")

                # Get bot token from settings
                api_token = settings.OPENAI_API_KEY

                # Create or update bot
                digital_twin = DigitalTwin.objects.create(
                    user_profile=profile,
                    # name=bot_config['display_name'],
                    persona=persona_description,
                    is_active=file_path in active_files,  # Only activate selected bots
                    api_token=None,
                )
                self.stdout.write(f"Created digital twin: {bot_config['display_name']} (Active: {digital_twin.is_active})")

            except Exception as e:
                self.stderr.write(f"Error setting up digital twin from {file_path}: {e!s}")

        self.stdout.write(self.style.SUCCESS("Successfully set up digital twins"))
