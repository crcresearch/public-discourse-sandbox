from django.core.management.base import BaseCommand
from public_discourse_sandbox.pds_app.tasks import generate_digital_twin_post
import uuid


class Command(BaseCommand):
    help = 'Generates a new post from a random DigitalTwin'

    def add_arguments(self, parser):
        parser.add_argument(
            '--experiment', 
            type=str, 
            dest='experiment_id',
            help='Optional experiment ID to filter the digital twins',
            required=False
        )
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            help='Force post generation, bypassing the should_post check',
            default=False
        )

    def handle(self, *args, **options):
        experiment_id = options.get('experiment_id')
        force = options.get('force')
        
        if experiment_id:
            try:
                # Validate that it's a valid UUID
                experiment_id = uuid.UUID(experiment_id)
                self.stdout.write(f"Generating post for a digital twin in experiment {experiment_id}")
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid experiment ID format: {experiment_id}"))
                return
        else:
            self.stdout.write("Generating post for a random digital twin from any experiment")
        
        if force:
            self.stdout.write("Forcing post generation (bypassing should_post check)")
        
        # Run the task asynchronously using Celery
        # .delay() is shorthand for .apply_async() without extra options
        result = generate_digital_twin_post.delay(experiment_id=experiment_id, force=force)
        
        if result:
            self.stdout.write(self.style.SUCCESS(f"Successfully generated digital twin post with ID: {result}"))
        else:
            self.stderr.write(self.style.ERROR("Failed to generate digital twin post")) 