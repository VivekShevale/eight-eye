from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.helpers import AccountHelper
from apps.accounts.serializers import LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(APIView):
    """POST: create a customer account."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AccountHelper.register_user(serializer.validated_data)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """POST: email + password -> access and refresh tokens."""

    serializer_class = LoginSerializer


class MeView(APIView):
    """GET: the authenticated user."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)
