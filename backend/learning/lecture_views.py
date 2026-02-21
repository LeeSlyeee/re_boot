"""
강의(Lecture) 관련 Views: 공개 목록, 내 강의, 수강 등록
"""
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

from .models import Lecture
from .serializers import PublicLectureSerializer


class PublicLectureListView(generics.ListAPIView):
    queryset = Lecture.objects.all().order_by('-created_at')
    serializer_class = PublicLectureSerializer
    # [Change] Allow browsing without strict auth for debugging, or ensure frontend token is valid
    permission_classes = [AllowAny]


class MyLectureListView(generics.ListAPIView):
    serializer_class = PublicLectureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.enrolled_lectures.all().order_by('-created_at')


class EnrollLectureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        access_code = request.data.get('access_code')
        if not access_code:
            return Response({'error': 'Access code is required'}, status=status.HTTP_400_BAD_REQUEST)

        lecture = get_object_or_404(Lecture, access_code=access_code)

        # [BUGFIX] 실제 수강 등록 수행 (이전에 누락되어 있었음)
        if lecture.students.filter(id=request.user.id).exists():
            return Response({'message': '이미 등록된 강의입니다.', 'lecture_id': lecture.id, 'title': lecture.title}, status=status.HTTP_200_OK)

        lecture.students.add(request.user)

        return Response({'message': 'Enrolled successfully', 'lecture_id': lecture.id, 'title': lecture.title}, status=status.HTTP_200_OK)
