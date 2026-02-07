from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Count
from .models import Lecture, QuizAttempt
from .serializers import LectureSerializer

from users.models import User

class IsInstructor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.INSTRUCTOR

class LectureViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsInstructor]
    serializer_class = LectureSerializer

    def get_queryset(self):
        # 교수가 개설한 강의만 조회
        if self.request.user.role != User.Role.INSTRUCTOR:
            return Lecture.objects.none()
        return Lecture.objects.filter(instructor=self.request.user)

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)

    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        lecture = self.get_object()
        students = lecture.students.all()
        
        data = []
        for student in students:
            # 해당 학생의 퀴즈 성적 집계
            # (Note: This aggregates ALL quizzes, might want to filter by course section if lecture is linked to one?)
            # For now, simplistic approach: All quiz attempts by this student.
            # Ideally, we should filter by quizzes related to the lecture content.
            # But Lecture -> ?? -> Content is not strictly defined yet.
            # We will just show all quiz stats for now.
            
            attempts = QuizAttempt.objects.filter(student=student)
            avg_score = attempts.aggregate(Avg('score'))['score__avg'] or 0
            quiz_count = attempts.count()
            
            latest_attempt = attempts.order_by('-submitted_at').first()
            latest_score = latest_attempt.score if latest_attempt else 0
            
            data.append({
                'id': student.id,
                'name': student.username, 
                'email': student.email,
                'average_score': round(avg_score, 1),
                'quiz_count': quiz_count,
                'latest_score': latest_score
            })
            
        return Response(data)
