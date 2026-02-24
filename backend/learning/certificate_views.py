"""
수료증 API: 클래스별 수료증 데이터 조회 + PDF 생성
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import Lecture, LearningSession
from .models.quiz import DailyQuiz
import pytz
from datetime import datetime


class CertificateDataView(APIView):
    """
    GET /api/learning/certificate/<lecture_id>/
    수료증에 필요한 학습 데이터 반환
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        user = request.user
        lecture = get_object_or_404(Lecture, id=lecture_id)

        # 수강 등록 확인
        if not lecture.students.filter(id=user.id).exists():
            return Response({'error': '등록된 수강생이 아닙니다.'}, status=status.HTTP_403_FORBIDDEN)

        # 세션 통계
        sessions = LearningSession.objects.filter(student=user, lecture=lecture)
        completed_sessions = sessions.filter(is_completed=True)
        total_seconds = 0
        for s in completed_sessions:
            if s.end_time and s.start_time:
                total_seconds += (s.end_time - s.start_time).total_seconds()

        total_hours = round(total_seconds / 3600, 1)

        # 출석률
        all_dates = set(
            LearningSession.objects.filter(lecture=lecture)
            .values_list('session_date', flat=True).distinct()
        )
        my_dates = set(
            sessions.values_list('session_date', flat=True).distinct()
        )
        attended = len(my_dates & all_dates)
        total_days = len(all_dates)
        attendance_rate = round((attended / total_days * 100), 1) if total_days > 0 else 0

        # 퀴즈 평균
        quizzes = DailyQuiz.objects.filter(student=user)
        quiz_scores = [q.total_score for q in quizzes if q.total_score is not None]
        avg_quiz = round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else 0

        # 종강 여부
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst).date()
        is_completed = bool(lecture.end_date and now >= lecture.end_date)

        return Response({
            'lecture_title': lecture.title,
            'instructor_name': lecture.instructor.username,
            'student_name': user.username,
            'start_date': str(lecture.start_date) if lecture.start_date else None,
            'end_date': str(lecture.end_date) if lecture.end_date else None,
            'total_hours': total_hours,
            'completed_sessions': completed_sessions.count(),
            'attendance_rate': attendance_rate,
            'attended_days': attended,
            'total_days': total_days,
            'avg_quiz_score': avg_quiz,
            'is_completed': is_completed,
            'issued_date': datetime.now(kst).strftime('%Y년 %m월 %d일'),
        })
