"""
매니저 대시보드 및 시각화 데이터 피딩 API
============================================
구현계획서 미완 항목:
  - [ ] 시각화 데이터 피딩용 API 고도화
  - [ ] 강사/매니저용 전체 대시보드 및 클래스 모니터링 툴

Endpoints:
  GET /api/learning/manager/dashboard/               → 매니저 전체 현황 대시보드
  GET /api/learning/manager/class/{id}/               → 클래스별 상세 모니터링
  GET /api/learning/manager/class/{id}/at-risk/       → 이탈 위험군 학생 목록
  GET /api/learning/visualization/student-progress/   → 학생 진도 시각화 데이터
  GET /api/learning/visualization/quiz-analytics/     → 퀴즈 성적 분석 데이터
  GET /api/learning/visualization/skill-heatmap/      → 스킬 히트맵 데이터
  GET /api/learning/visualization/engagement/         → 학습 참여도 트렌드 데이터
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Q, F, Sum, Max, Min
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from users.models import User, ClassGroup, Enrollment
from learning.models import (
    Lecture, LearningSession, QuizAttempt, DailyQuiz,
    LiveSession, LiveParticipant, SkillBlock, StudentSkill,
    FormativeAssessment, FormativeResponse,
)


class ManagerDashboardView(APIView):
    """
    매니저 전체 현황 대시보드.
    - 관리 중인 클래스 전체 요약
    - 전체 학생 수, 평균 성취율, 이탈 위험군 수
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # 매니저가 관리하는 모든 클래스
        managed_classes = ClassGroup.objects.filter(manager=user)

        # 강사가 가르치는 강의들
        teaching_lectures = Lecture.objects.filter(instructor=user)

        # 관련 학생 수집
        if managed_classes.exists():
            student_ids = Enrollment.objects.filter(
                class_group__in=managed_classes
            ).values_list('student_id', flat=True).distinct()
        elif teaching_lectures.exists():
            student_ids = User.objects.filter(
                enrolled_lectures__in=teaching_lectures
            ).values_list('id', flat=True).distinct()
        else:
            student_ids = []

        total_students = len(set(student_ids))

        # 퀴즈 평균 점수
        avg_quiz = QuizAttempt.objects.filter(
            student_id__in=student_ids
        ).aggregate(avg_score=Avg('score'))['avg_score'] or 0

        # 최근 7일 학습 세션 수
        week_ago = timezone.now() - timedelta(days=7)
        recent_sessions = LearningSession.objects.filter(
            student_id__in=student_ids,
            start_time__gte=week_ago
        ).count()

        # 이탈 위험군: 최근 7일 활동 없는 학생
        active_student_ids = set(LearningSession.objects.filter(
            student_id__in=student_ids,
            start_time__gte=week_ago
        ).values_list('student_id', flat=True))
        at_risk_count = total_students - len(active_student_ids)

        # 스킬블록 획득 통계
        earned_blocks = SkillBlock.objects.filter(
            student_id__in=student_ids, is_earned=True
        ).count()
        total_blocks = SkillBlock.objects.filter(
            student_id__in=student_ids
        ).count()
        skill_completion_rate = (
            int((earned_blocks / total_blocks) * 100) if total_blocks > 0 else 0
        )

        # 클래스별 요약
        class_summaries = []
        for cls in managed_classes:
            enrolled = Enrollment.objects.filter(class_group=cls)
            class_student_ids = list(enrolled.values_list('student_id', flat=True))
            cls_avg = QuizAttempt.objects.filter(
                student_id__in=class_student_ids
            ).aggregate(avg=Avg('score'))['avg'] or 0

            class_summaries.append({
                'id': cls.id,
                'name': cls.name,
                'student_count': len(class_student_ids),
                'avg_score': round(cls_avg, 1),
                'start_date': cls.start_date.isoformat(),
                'end_date': cls.end_date.isoformat(),
            })

        # 강의별 요약 (강사용)
        lecture_summaries = []
        for lec in teaching_lectures:
            lec_students = lec.students.count()
            lecture_summaries.append({
                'id': lec.id,
                'title': lec.title,
                'student_count': lec_students,
                'access_code': lec.access_code,
            })

        return Response({
            'total_students': total_students,
            'avg_quiz_score': round(avg_quiz, 1),
            'recent_sessions_7d': recent_sessions,
            'at_risk_count': at_risk_count,
            'skill_completion_rate': skill_completion_rate,
            'classes': class_summaries,
            'lectures': lecture_summaries,
            'generated_at': timezone.now().isoformat(),
        })


class ClassMonitorView(APIView):
    """클래스별 상세 모니터링"""
    permission_classes = [IsAuthenticated]

    def get(self, request, class_id):
        try:
            cls = ClassGroup.objects.get(id=class_id)
        except ClassGroup.DoesNotExist:
            return Response({'error': '클래스를 찾을 수 없습니다.'}, status=404)

        enrollments = Enrollment.objects.filter(
            class_group=cls
        ).select_related('student')
        student_ids = [e.student_id for e in enrollments]

        week_ago = timezone.now() - timedelta(days=7)

        students_data = []
        for enrollment in enrollments:
            sid = enrollment.student_id
            student = enrollment.student

            # 퀴즈 성적
            quiz_stats = QuizAttempt.objects.filter(
                student_id=sid
            ).aggregate(
                avg_score=Avg('score'),
                total_attempts=Count('id'),
            )

            # 최근 활동
            last_session = LearningSession.objects.filter(
                student_id=sid
            ).order_by('-start_time').first()

            # 스킬블록
            earned = SkillBlock.objects.filter(
                student_id=sid, is_earned=True
            ).count()
            total = SkillBlock.objects.filter(student_id=sid).count()

            # 이탈 위험 판정
            days_inactive = 0
            if last_session:
                days_inactive = (timezone.now() - last_session.start_time).days

            students_data.append({
                'student_id': sid,
                'username': student.username,
                'nickname': student.first_name or student.username,
                'avg_quiz_score': round(quiz_stats['avg_score'] or 0, 1),
                'total_quiz_attempts': quiz_stats['total_attempts'] or 0,
                'skill_blocks_earned': earned,
                'skill_blocks_total': total,
                'last_active': last_session.start_time.isoformat() if last_session else None,
                'days_inactive': days_inactive,
                'is_at_risk': days_inactive >= 7,
                'joined_at': enrollment.joined_at.isoformat(),
            })

        # 위험도 높은 학생 우선 정렬
        students_data.sort(key=lambda x: (-x['days_inactive'], x['avg_quiz_score']))

        return Response({
            'class_id': cls.id,
            'class_name': cls.name,
            'total_students': len(students_data),
            'at_risk_students': sum(1 for s in students_data if s['is_at_risk']),
            'students': students_data,
        })


class AtRiskStudentsView(APIView):
    """이탈 위험군 학생 목록"""
    permission_classes = [IsAuthenticated]

    def get(self, request, class_id):
        try:
            cls = ClassGroup.objects.get(id=class_id)
        except ClassGroup.DoesNotExist:
            return Response({'error': '클래스를 찾을 수 없습니다.'}, status=404)

        enrollments = Enrollment.objects.filter(
            class_group=cls
        ).select_related('student')

        week_ago = timezone.now() - timedelta(days=7)
        at_risk = []

        for enrollment in enrollments:
            sid = enrollment.student_id
            last_session = LearningSession.objects.filter(
                student_id=sid
            ).order_by('-start_time').first()

            if not last_session or (timezone.now() - last_session.start_time).days >= 7:
                days_inactive = (
                    (timezone.now() - last_session.start_time).days
                    if last_session else 999
                )

                # 최근 퀴즈 성적 하락 체크
                recent_quizzes = QuizAttempt.objects.filter(
                    student_id=sid
                ).order_by('-submitted_at')[:5]
                avg_recent = sum(q.score for q in recent_quizzes) / len(recent_quizzes) if recent_quizzes else 0

                at_risk.append({
                    'student_id': sid,
                    'username': enrollment.student.username,
                    'nickname': enrollment.student.first_name or enrollment.student.username,
                    'days_inactive': days_inactive,
                    'last_active': last_session.start_time.isoformat() if last_session else '없음',
                    'recent_avg_score': round(avg_recent, 1),
                    'risk_level': 'HIGH' if days_inactive >= 14 else 'MEDIUM',
                    'risk_factors': self._get_risk_factors(sid, days_inactive, avg_recent),
                })

        at_risk.sort(key=lambda x: -x['days_inactive'])

        return Response({
            'class_id': cls.id,
            'class_name': cls.name,
            'at_risk_students': at_risk,
            'total_at_risk': len(at_risk),
        })

    def _get_risk_factors(self, student_id, days_inactive, avg_score):
        factors = []
        if days_inactive >= 14:
            factors.append('2주 이상 미접속')
        elif days_inactive >= 7:
            factors.append('1주 이상 미접속')
        if avg_score < 60:
            factors.append('퀴즈 평균 60점 미만')
        if avg_score == 0:
            factors.append('퀴즈 미응시')

        failed_count = QuizAttempt.objects.filter(
            student_id=student_id, score__lt=60
        ).count()
        if failed_count >= 3:
            factors.append(f'퀴즈 {failed_count}회 낙제')

        return factors


# ═══════════════════════════════════════════════
# 시각화 데이터 피딩 API
# ═══════════════════════════════════════════════

class StudentProgressVisualization(APIView):
    """
    학생 진도 시각화 데이터.
    차트에 바로 바인딩할 수 있는 형태로 반환.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lecture_id = request.query_params.get('lecture_id')
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        # 대상 학생 결정
        if lecture_id:
            student_ids = Lecture.objects.get(id=lecture_id).students.values_list('id', flat=True)
        else:
            student_ids = User.objects.filter(
                enrolled_lectures__instructor=request.user
            ).values_list('id', flat=True).distinct()

        if not student_ids:
            return Response({'labels': [], 'datasets': []})

        # 일별 학습 세션 수 (차트 데이터)
        daily_sessions = (
            LearningSession.objects.filter(
                student_id__in=student_ids,
                start_time__gte=start_date,
            )
            .extra(select={'date': "DATE(start_time)"})
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        labels = [str(d['date']) for d in daily_sessions]
        counts = [d['count'] for d in daily_sessions]

        # 일별 평균 퀴즈 점수
        daily_quiz = (
            QuizAttempt.objects.filter(
                student_id__in=student_ids,
                submitted_at__gte=start_date,
            )
            .extra(select={'date': "DATE(submitted_at)"})
            .values('date')
            .annotate(avg_score=Avg('score'))
            .order_by('date')
        )

        quiz_labels = [str(d['date']) for d in daily_quiz]
        quiz_scores = [round(d['avg_score'], 1) for d in daily_quiz]

        return Response({
            'sessions': {
                'labels': labels,
                'datasets': [{'label': '일별 학습 세션', 'data': counts}],
            },
            'quiz_scores': {
                'labels': quiz_labels,
                'datasets': [{'label': '일별 평균 퀴즈 점수', 'data': quiz_scores}],
            },
            'period_days': days,
        })


class QuizAnalyticsVisualization(APIView):
    """퀴즈 성적 분석 시각화 데이터"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lecture_id = request.query_params.get('lecture_id')

        if lecture_id:
            student_ids = Lecture.objects.get(id=lecture_id).students.values_list('id', flat=True)
        else:
            student_ids = User.objects.filter(
                enrolled_lectures__instructor=request.user
            ).values_list('id', flat=True).distinct()

        # 점수 분포 (히스토그램)
        attempts = QuizAttempt.objects.filter(student_id__in=student_ids)
        score_ranges = {
            '0-20': 0, '21-40': 0, '41-60': 0,
            '61-80': 0, '81-100': 0,
        }
        for attempt in attempts:
            if attempt.score <= 20:
                score_ranges['0-20'] += 1
            elif attempt.score <= 40:
                score_ranges['21-40'] += 1
            elif attempt.score <= 60:
                score_ranges['41-60'] += 1
            elif attempt.score <= 80:
                score_ranges['61-80'] += 1
            else:
                score_ranges['81-100'] += 1

        # 학생별 평균 점수 (순위)
        student_averages = (
            QuizAttempt.objects.filter(student_id__in=student_ids)
            .values('student__username')
            .annotate(avg_score=Avg('score'), attempt_count=Count('id'))
            .order_by('-avg_score')[:20]
        )

        # 통과율
        total_attempts = attempts.count()
        passed = attempts.filter(score__gte=60).count()
        pass_rate = round((passed / total_attempts) * 100, 1) if total_attempts > 0 else 0

        return Response({
            'score_distribution': {
                'labels': list(score_ranges.keys()),
                'data': list(score_ranges.values()),
            },
            'student_rankings': list(student_averages),
            'pass_rate': pass_rate,
            'total_attempts': total_attempts,
        })


class SkillHeatmapVisualization(APIView):
    """스킬 히트맵 시각화 데이터"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lecture_id = request.query_params.get('lecture_id')

        if lecture_id:
            student_ids = Lecture.objects.get(id=lecture_id).students.values_list('id', flat=True)
        else:
            student_ids = User.objects.filter(
                enrolled_lectures__instructor=request.user
            ).values_list('id', flat=True).distinct()

        # 학생별 스킬 보유 매트릭스
        skills = StudentSkill.objects.filter(
            student_id__in=student_ids
        ).select_related('skill', 'student')

        heatmap_data = {}
        for ss in skills:
            student_name = ss.student.username
            skill_name = ss.skill.name if ss.skill else 'Unknown'
            if student_name not in heatmap_data:
                heatmap_data[student_name] = {}
            heatmap_data[student_name][skill_name] = {
                'status': ss.status,
                'progress': ss.progress,
            }

        # 스킬별 획득률
        all_skills = StudentSkill.objects.filter(
            student_id__in=student_ids
        ).values('skill__name').annotate(
            owned_count=Count('id', filter=Q(status='OWNED')),
            total_count=Count('id'),
        )

        skill_completion = [
            {
                'skill': s['skill__name'],
                'completion_rate': round(
                    (s['owned_count'] / s['total_count']) * 100, 1
                ) if s['total_count'] > 0 else 0,
                'owned': s['owned_count'],
                'total': s['total_count'],
            }
            for s in all_skills
        ]

        return Response({
            'heatmap': heatmap_data,
            'skill_completion': skill_completion,
        })


class EngagementVisualization(APIView):
    """학습 참여도 트렌드 데이터"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lecture_id = request.query_params.get('lecture_id')
        days = int(request.query_params.get('days', 14))
        start_date = timezone.now() - timedelta(days=days)

        if lecture_id:
            student_ids = Lecture.objects.get(id=lecture_id).students.values_list('id', flat=True)
        else:
            student_ids = User.objects.filter(
                enrolled_lectures__instructor=request.user
            ).values_list('id', flat=True).distinct()

        total_students = len(set(student_ids))

        # 일별 참여 학생 수 (출석률 개념)
        daily_engagement = []
        for d in range(days):
            date = (timezone.now() - timedelta(days=days - 1 - d)).date()
            active = LearningSession.objects.filter(
                student_id__in=student_ids,
                start_time__date=date,
            ).values('student_id').distinct().count()

            daily_engagement.append({
                'date': str(date),
                'active_students': active,
                'engagement_rate': round(
                    (active / total_students) * 100, 1
                ) if total_students > 0 else 0,
            })

        # 시간대별 학습 패턴
        hourly_pattern = (
            LearningSession.objects.filter(
                student_id__in=student_ids,
                start_time__gte=start_date,
            )
            .extra(select={'hour': "EXTRACT(HOUR FROM start_time)"})
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )

        return Response({
            'daily_engagement': daily_engagement,
            'hourly_pattern': list(hourly_pattern),
            'total_students': total_students,
            'period_days': days,
        })
