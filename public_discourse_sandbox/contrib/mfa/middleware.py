"""
Middleware to enforce MFA for all users.
"""
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class AllUserRequire2FAMiddleware(MiddlewareMixin):
    """
    Ensure that all users have two-factor authentication enabled before
    they have access to the rest of the app.

    If they don't have 2FA enabled, they will be redirected to the 2FA
    enrollment page and not be allowed to access other pages.
    """

    # List of URL names that the user should still be allowed to access.
    allowed_pages = [
        # They should still be able to log out or change password.
        "account_login",
        "account_logout",
        "account_reauthenticate",
        "account_reset_password_done",
        "account_reset_password_from_key",
        "account_reset_password_from_key_done",
        "account_reset_password",
        "account_email",
        "account_email_verification_sent",
        "account_confirm_email",
        "mfa_activate_totp",
    ]
    # The message to the user if they don't have 2FA enabled and must enable it.
    require_2fa_message = (
        "You must enable two-factor authentication before doing anything else."
    )

    def on_require_2fa(self, request: HttpRequest) -> HttpResponse:
        """
        If the current request requires 2FA and the user does not have it
        enabled, this is executed. The result of this is returned from the
        middleware.
        """
        # See allauth.account.adapter.DefaultAccountAdapter.add_message.
        if "django.contrib.messages" in settings.INSTALLED_APPS:
            # If there is already a pending message related to two-factor (likely
            # created by a redirect view), simply update the message text.
            storage = messages.get_messages(request)
            tag = "2fa_required"
            for m in storage:
                if m.extra_tags == tag:
                    m.message = self.require_2fa_message
                    break
            # Otherwise, create a new message.
            else:
                messages.error(request, self.require_2fa_message, extra_tags=tag)
            # Mark the storage as not processed so they'll be shown to the user.
            storage.used = False

        # Redirect user to two-factor setup page.
        return redirect("mfa_activate_totp")

    def is_allowed_page(self, request: HttpRequest) -> bool:
        return request.resolver_match.url_name in self.allowed_pages

    def process_view(
        self,
        request: HttpRequest,
        view_func,
        view_args,
        view_kwargs,
    ) -> HttpResponse | None:
        # The user is not logged in, do nothing.
        if request.user.is_anonymous:
            return None

        # If the user is on one of the allowed pages, do nothing.
        if self.is_allowed_page(request):
            return None

        # User already has two-factor configured, do nothing.
        if is_mfa_enabled(request.user):
            return None

        # The request required 2FA but it isn't configured!
        return self.on_require_2fa(request) 