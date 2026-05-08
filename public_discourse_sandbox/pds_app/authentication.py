from rest_framework.authentication import TokenAuthentication

from .models import AuthApiToken


class BearerAuthentication(TokenAuthentication):
    model = AuthApiToken
    keyword = "Bearer"
