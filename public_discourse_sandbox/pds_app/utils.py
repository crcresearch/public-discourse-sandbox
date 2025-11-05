import logging

from django.utils import timezone
from django_notification_system.models import Notification as DjNotification
from django_notification_system.models import TargetUserRecord
from profanity_check import predict_prob
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def check_profanity(text, threshold=0.75):
    """
    Checks if the provided text contains profanity using alt-profanity-check.

    Args:
        text: The text to check for profanity
        threshold: The probability threshold above which the text is considered profane (default: 0.75)

    Returns:
        Boolean indicating whether the text contains profanity
    """
    if not text:
        return False

    # Get profanity probability from the model
    probability = predict_prob([text])[0]

    # Return True if probability is above threshold
    return probability > threshold


def send_notification_to_user(
    user_profile,
    title: str,
    body: str,
    status: str = "SCHEDULED",
) -> None:
    """
    Sends notifications to all notification targets for a given user profile.
    This function fetches all TargetUserRecords for the user and creates a
    DjNotification for each one.

    Args:
        user_profile: The UserProfile instance to send notifications to
        title (str): The notification title
        body (str): The notification body/message
        status (str): The notification status (default: "SCHEDULED")
    """
    notification_targets = TargetUserRecord.objects.filter(
        user=user_profile.user,
        active=True,
    )

    if notification_targets.exists():
        for target in notification_targets:
            try:
                html_content = render_to_string(
                    "email/updates_email.html",
                    {"username": user_profile.username, "body": body},
                )
                DjNotification.objects.create(
                    target_user_record=target,
                    title=title,
                    body=html_content
                    if "twilio" not in target.description
                    else f"You've received a new notification on https://publicdiscourse.crc.nd.edu. {body}. Sign in to view more details.",
                    status=status,
                    scheduled_delivery=timezone.now(),
                )
                logger.debug(
                    f"Created notification for user {user_profile.username} "
                    f"target {target.target_user_id}",
                )
            except Exception as e:
                logger.exception(e)
