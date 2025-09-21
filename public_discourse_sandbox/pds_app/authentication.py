from rest_framework.authentication import TokenAuthentication

from .models import MultiToken


class BearerAuthentication(TokenAuthentication):
    model = MultiToken
    keyword = "Bearer"
