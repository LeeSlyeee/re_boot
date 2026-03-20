"""
사용자 인증 및 정보 관련 Views
"""
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class DemoLoginView(APIView):
    """
    [프레젠테이션 전용] 로그인 없이 현장 강의 테스트를 위한 게스트 로그인.
    호출 시마다 고유한 demo_XXXX 유저를 생성하여 JWT 토큰을 반환한다.
    20명+ 동시 사용 지원 (각자 독립된 세션).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        import uuid
        short_id = uuid.uuid4().hex[:8]
        username = f'demo_{short_id}'

        demo_user = User.objects.create_user(
            username=username,
            password=uuid.uuid4().hex,  # 랜덤 패스워드 (직접 로그인 불가)
            email=f'{username}@demo.reboot.local',
            role='STUDENT',
            goal_type='프레젠테이션',
        )

        # SimpleJWT 토큰 발급
        refresh = RefreshToken.for_user(demo_user)
        return Response({
            'access': str(refresh.access_token),
            'user': UserSerializer(demo_user).data,
        }, status=status.HTTP_200_OK)
