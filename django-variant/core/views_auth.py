from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserAccount

class LoginView(APIView):
    permission_classes = []
    def post(self, request):
        user = UserAccount.objects.filter(email=request.data.get("email")).first()
        if not user or not check_password(request.data.get("password"), user.password_hash):
            return Response({"detail": "Invalid credentials"}, status=401)
        refresh = RefreshToken()
        refresh["user_id"] = str(user.id)
        refresh["org_id"] = str(user.org_id)
        refresh["role"] = user.role
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})
