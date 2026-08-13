from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import UserAccount

class UserAccountJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            user = UserAccount.objects.get(id=validated_token["user_id"])
        except UserAccount.DoesNotExist:
            return None
        user.is_authenticated = True  # DRF's only real requirement
        return user
