from ninja.security import HttpBearer
from django.conf import settings

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        if token == settings.BOT_SHARED_SECRET:
            return token
        return None