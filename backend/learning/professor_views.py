from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Count, Q, F
from django.db.models.functions import TruncDate
from .models import (
    Lecture, QuizAttempt, LearningSession, LearningObjective,
    StudentChecklist, DailyQuiz, QuizQuestion, AttemptDetail,
    RecordingUpload
)
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
        
        total_objectives = LearningObjective.objects.filter(syllabus__lecture=lecture).count()
        
        monitor_data = []
        
        for student in students:
            checked_qs = StudentChecklist.objects.filter(
                student=student, 
                objective__syllabus__lecture=lecture, 
                is_checked=True
            ).select_related('objective')
            
            checked_count = checked_qs.count()
            progress = (checked_count / total_objectives * 100) if total_objectives > 0 else 0
            
            status_level = 'good'
            if progress < 30:
                status_level = 'critical'
            elif progress < 60:
                status_level = 'warning'
                
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
            
        status_priority = {'critical': 0, 'warning': 1, 'good': 2}
        monitor_data.sort(key=lambda x: status_priority.get(x['status'], 3))
            
        return Response(monitor_data)

    # ──────────────────────────────────────────
    # [NEW] 출석률 현황 API
    # ──────────────────────────────────────────
    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        """
        강의별 학생 출석률 집계
        
        Response:
        {
            "summary": {
                "total_students": 25,
                "total_dates": 10,
                "overall_rate": 85.2
            },
            "dates": ["2026-02-10", "2026-02-11", ...],
            "students": [
                {
                    "id": 1, "name": "홍길동",
                    "attended_count": 8, "total_dates": 10,
                    "rate": 80.0,
                    "daily": {"2026-02-10": true, "2026-02-11": false, ...}
                }, ...
            ]
        }
        """
        lecture = self.get_object()
        students = lecture.students.all()
        
        # 이 강의에 속한 모든 세션의 날짜 목록 (중복 제거, 정렬)
        all_dates = (
            LearningSession.objects
            .filter(lecture=lecture)
            .values_list('session_date', flat=True)
            .distinct()
            .order_by('session_date')
        )
        date_list = list(all_dates)
        total_dates = len(date_list)
        
        student_data = []
        total_attendance_sum = 0
        
        for student in students:
            # 이 학생이 출석한 날짜 목록
            attended_dates = set(
                LearningSession.objects
                .filter(lecture=lecture, student=student)
                .values_list('session_date', flat=True)
                .distinct()
            )
            
            attended_count = len(attended_dates)
            rate = (attended_count / total_dates * 100) if total_dates > 0 else 0
            total_attendance_sum += rate
            
            # 날짜별 출석 여부 딕셔너리
            daily = {}
            for d in date_list:
                daily[str(d)] = d in attended_dates
            
            student_data.append({
                'id': student.id,
                'name': student.username,
                'email': student.email,
                'attended_count': attended_count,
                'total_dates': total_dates,
                'rate': round(rate, 1),
                'daily': daily
            })
        
        # 출석률 높은 순 정렬
        student_data.sort(key=lambda x: x['rate'], reverse=True)
        
        overall_rate = (total_attendance_sum / len(students)) if len(students) > 0 else 0
        
        return Response({
            'summary': {
                'total_students': len(students),
                'total_dates': total_dates,
                'overall_rate': round(overall_rate, 1)
            },
            'dates': [str(d) for d in date_list],
            'students': student_data
        })

    # ──────────────────────────────────────────
    # [NEW] 퀴즈 데이터 시각화 API
    # ──────────────────────────────────────────
    @action(detail=True, methods=['get'])
    def quiz_analytics(self, request, pk=None):
        """
        강의별 퀴즈 통계 분석
        
        Response:
        {
            "summary": {
                "total_quizzes": 50,
                "average_score": 72.5,
                "pass_rate": 68.0
            },
            "score_distribution": {
                "0-20": 2, "21-40": 5, "41-60": 10, "61-80": 20, "81-100": 13
            },
            "students": [
                {
                    "id": 1, "name": "홍길동",
                    "quiz_count": 5, "avg_score": 82.0,
                    "scores": [80, 75, 90, 85, 80]
                }, ...
            ],
            "question_accuracy": [
                {"question_text": "...", "accuracy": 75.0, "total_answers": 20}, ...
            ]
        }
        """
        lecture = self.get_object()
        students = lecture.students.all()
        student_ids = list(students.values_list('id', flat=True))
        
        # 전체 퀴즈 시도 (해당 강의 수강생들의 것만)
        all_attempts = QuizAttempt.objects.filter(student_id__in=student_ids)
        
        total_quizzes = all_attempts.count()
        avg_score_val = all_attempts.aggregate(Avg('score'))['score__avg'] or 0
        
        # 합격률 (60점 이상을 합격으로 간주)
        pass_count = all_attempts.filter(score__gte=60).count()
        pass_rate = (pass_count / total_quizzes * 100) if total_quizzes > 0 else 0
        
        # 점수 분포 (5구간)
        distribution = {
            '0-20': all_attempts.filter(score__lte=20).count(),
            '21-40': all_attempts.filter(score__gt=20, score__lte=40).count(),
            '41-60': all_attempts.filter(score__gt=40, score__lte=60).count(),
            '61-80': all_attempts.filter(score__gt=60, score__lte=80).count(),
            '81-100': all_attempts.filter(score__gt=80).count(),
        }
        
        # 학생별 성적 추이
        student_stats = []
        for student in students:
            attempts = all_attempts.filter(student=student).order_by('submitted_at')
            scores = list(attempts.values_list('score', flat=True))
            avg = sum(scores) / len(scores) if scores else 0
            
            student_stats.append({
                'id': student.id,
                'name': student.username,
                'quiz_count': len(scores),
                'avg_score': round(avg, 1),
                'scores': scores
            })
        
        # 평균 점수 높은 순 정렬
        student_stats.sort(key=lambda x: x['avg_score'], reverse=True)
        
        # 문항별 정답률 (최근 퀴즈 기준, 상위 10개 문항)
        question_accuracy = []
        recent_details = (
            AttemptDetail.objects
            .filter(attempt__student_id__in=student_ids)
            .values('question_id', 'question__question_text')
            .annotate(
                total_answers=Count('id'),
                correct_answers=Count('id', filter=Q(is_correct=True))
            )
            .order_by('-total_answers')[:10]
        )
        
        for detail in recent_details:
            total = detail['total_answers']
            correct = detail['correct_answers']
            accuracy = (correct / total * 100) if total > 0 else 0
            question_accuracy.append({
                'question_text': detail['question__question_text'][:80],
                'accuracy': round(accuracy, 1),
                'total_answers': total
            })
        
        return Response({
            'summary': {
                'total_quizzes': total_quizzes,
                'average_score': round(avg_score_val, 1),
                'pass_rate': round(pass_rate, 1)
            },
            'score_distribution': distribution,
            'students': student_stats,
            'question_accuracy': question_accuracy
        })

    # ──────────────────────────────────────────
    # [NEW] 녹음 파일 업로드 → 가공 파이프라인
    # ──────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='upload_recording')
    def upload_recording(self, request, pk=None):
        """
        강의 녹음 파일 업로드 및 가공 파이프라인 실행
        
        1시간 강의 기준 설계 (mp3 ~60MB, wav ~600MB → 변환 후 처리)
        
        Request:
            FILES: { "audio_file": <UploadedFile> }
        
        Response (성공):
            {
                "recording_id": 1,
                "session_id": 42,
                "summary": "# 📚 강의 요약 ...",
                "duration_minutes": 60,
                "total_chunks": 4
            }
        """
        lecture = self.get_object()
        audio_file = request.FILES.get('audio_file')
        
        if not audio_file:
            return Response(
                {"error": "오디오 파일이 제공되지 않았습니다."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 파일 크기 제한 (150MB — 1시간 wav도 커버)
        MAX_SIZE = 150 * 1024 * 1024
        if audio_file.size > MAX_SIZE:
            return Response(
                {"error": f"파일 크기가 {MAX_SIZE // (1024*1024)}MB를 초과합니다. 현재: {audio_file.size // (1024*1024)}MB"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # RecordingUpload 레코드 생성
        recording = RecordingUpload.objects.create(
            lecture=lecture,
            uploaded_by=request.user,
            audio_file=audio_file,
            original_filename=audio_file.name,
            file_size=audio_file.size,
        )
        
        # 동기 처리 (선택지 A)
        from .recording_pipeline import process_recording
        result = process_recording(recording.id)
        
        if result.get('success'):
            return Response({
                'recording_id': recording.id,
                'session_id': result['session_id'],
                'summary': result['summary'],
                'duration_minutes': result.get('duration_minutes', 0),
                'total_chunks': result.get('total_chunks', 0),
                'stt_length': result.get('stt_length', 0),
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'recording_id': recording.id,
                'error': result.get('error', '알 수 없는 오류가 발생했습니다.'),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='recordings')
    def recordings(self, request, pk=None):
        """
        해당 강의의 녹음 업로드 이력 조회
        """
        lecture = self.get_object()
        uploads = RecordingUpload.objects.filter(lecture=lecture)
        
        data = []
        for r in uploads:
            data.append({
                'id': r.id,
                'filename': r.original_filename,
                'file_size_mb': round(r.file_size / (1024 * 1024), 1),
                'duration_minutes': (r.duration_seconds // 60) if r.duration_seconds else None,
                'status': r.status,
                'progress': r.progress,
                'session_id': r.session_id,
                'error_message': r.error_message,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
                'completed_at': r.completed_at.strftime('%Y-%m-%d %H:%M') if r.completed_at else None,
            })
        
        return Response(data)
