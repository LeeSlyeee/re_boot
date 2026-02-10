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

    @action(detail=True, methods=['get'])
    def monitor(self, request, pk=None):
        """
        [Real-time Monitoring]
        수강생들의 진도율, 위험 상태(Critical/Warning), 최근 획득 스킬 조회
        """
        lecture = self.get_object()
        students = lecture.students.all()
        
        # 1. Total Objectives Count
        from .models import LearningObjective, StudentChecklist
        total_objectives = LearningObjective.objects.filter(syllabus__lecture=lecture).count()
        
        monitor_data = []
        
        for student in students:
            # 2. Student Progress
            checked_qs = StudentChecklist.objects.filter(
                student=student, 
                objective__syllabus__lecture=lecture, 
                is_checked=True
            ).select_related('objective')
            
            checked_count = checked_qs.count()
            progress = (checked_count / total_objectives * 100) if total_objectives > 0 else 0
            
            # 3. Determine Status
            status_level = 'good'
            if progress < 30:
                status_level = 'critical'
            elif progress < 60:
                status_level = 'warning'
                
            # 4. Recent Skills (Top 3)
            recent_skills = [
                check.objective.content 
                for check in checked_qs.order_by('-updated_at')[:3]
            ]
            
            monitor_data.append({
                'id': student.id,
                'name': student.username,
                'email': student.email,
                'progress': round(progress, 1),
                'status': status_level,
                'recent_skills': recent_skills,
                'checked_count': checked_count,
                'total_count': total_objectives
            })
            
        # Sort by status priority (Critical -> Warning -> Good)
        status_priority = {'critical': 0, 'warning': 1, 'good': 2}
        monitor_data.sort(key=lambda x: status_priority.get(x['status'], 3))
            
        return Response(monitor_data)
