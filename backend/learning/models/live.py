"""
라이브 세션 관련 모델: LiveSession, LiveParticipant, LectureMaterial,
LiveSTTLog, PulseCheck, PulseLog, LiveQuiz, LiveQuizResponse,
LiveQuestion, LiveSessionNote, WeakZoneAlert
"""
from django.db import models
from django.conf import settings
from .base import Lecture
from .session import LearningSession
import random
import string


# ══════════════════════════════════════════════════════════
# Phase 0: 라이브 세션 인프라 모델
# ══════════════════════════════════════════════════════════

class LiveSession(models.Model):
    """
    교수자가 시작하는 실시간 수업 세션.
    학생들은 session_code로 입장하여 참여한다.
    """
    STATUS_CHOICES = (
        ('WAITING', '대기 중'),
        ('LIVE', '진행 중'),
        ('ENDED', '종료됨'),
    )

    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='live_sessions')
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_live_sessions')
    title = models.CharField(max_length=200, blank=True, help_text="세션 제목 (예: Week 3 - Django ORM)")
    session_code = models.CharField(max_length=6, unique=True, blank=True, help_text="학생 입장용 6자리 코드")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='WAITING')
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.session_code:
            self.session_code = self._generate_unique_code()
        super().save(*args, **kwargs)

    def _generate_unique_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(6))
            if not LiveSession.objects.filter(session_code=code).exists():
                return code

    def __str__(self):
        return f"[{self.status}] {self.title or self.lecture.title} ({self.session_code})"


class LiveParticipant(models.Model):
    """
    라이브 세션에 참여한 학생 기록.
    입장 시 개인 LearningSession이 자동 생성되어 연결된다.
    """
    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='participants')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='live_participations')
    learning_session = models.ForeignKey(
        LearningSession, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="입장 시 자동 생성되는 개인 학습 세션"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, help_text="현재 접속 중 여부 (heartbeat 기반)")
    last_heartbeat = models.DateTimeField(auto_now=True, help_text="마지막 활동 시간")

    class Meta:
        app_label = 'learning'
        unique_together = ['live_session', 'student']
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.student.username} @ {self.live_session.session_code}"


class LectureMaterial(models.Model):
    """
    강의 전 교수자가 업로드하는 교안 (PDF, PPT, 마크다운)
    """
    FILE_TYPE_CHOICES = (
        ('PDF', 'PDF'),
        ('PPT', 'PowerPoint'),
        ('MD', '마크다운'),
        ('OTHER', '기타'),
    )

    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200, help_text="교안 제목")
    file = models.FileField(upload_to='materials/%Y/%m/')
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default='PDF')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"[{self.file_type}] {self.title} ({self.lecture.title})"


class LiveSTTLog(models.Model):
    """
    라이브 세션 중 교수자 마이크에서 캡처된 STT 로그.
    기존 STTLog(학생 개인)와 구분되는 공유 STT 로그.
    """
    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='stt_logs')
    sequence_order = models.IntegerField()
    text_chunk = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['sequence_order']

    def __str__(self):
        return f"[{self.sequence_order}] {self.text_chunk[:30]}..."


class PulseCheck(models.Model):
    """
    학생의 실시간 이해도 펄스 (✅ 이해 / ❓ 혼란).
    동일 학생은 세션당 최신 1건만 유지 (unique_together + update_or_create).
    """
    PULSE_CHOICES = (
        ('UNDERSTAND', '이해'),
        ('CONFUSED', '혼란'),
    )

    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='pulses')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pulse_checks')
    pulse_type = models.CharField(max_length=12, choices=PULSE_CHOICES)
    created_at = models.DateTimeField(auto_now=True)  # auto_now: 매번 갱신

    class Meta:
        app_label = 'learning'
        unique_together = ['live_session', 'student']  # 세션당 학생 1건만

    def __str__(self):
        return f"{self.student.username}: {self.pulse_type} @ {self.live_session.session_code}"


class PulseLog(models.Model):
    """
    펄스 이력 (Weak Zone 감지용).
    PulseCheck은 '현재 상태' (unique_together), PulseLog은 '이력' (모두 기록).
    """
    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='pulse_logs')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pulse_log_entries')
    pulse_type = models.CharField(max_length=12, choices=PulseCheck.PULSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-created_at']

    def __str__(self):
        return f"[Log] {self.student.username}: {self.pulse_type} @ {self.created_at}"


class LiveQuiz(models.Model):
    """
    교수자가 라이브 세션 중 발동하는 체크포인트 퀴즈.
    AI가 자동 생성하거나, 교수자가 직접 입력할 수 있다.
    """
    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='quizzes')
    question_text = models.TextField(help_text="퀴즈 문제")
    options = models.JSONField(help_text="객관식 보기 리스트 (예: ['A답', 'B답', 'C답', 'D답'])")
    correct_answer = models.CharField(max_length=255, help_text="정답")
    explanation = models.TextField(blank=True, help_text="해설")
    is_ai_generated = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="현재 활성 퀴즈 여부")
    is_suggestion = models.BooleanField(default=False, help_text="AI 자동 제안 (교수자 미승인)")
    time_limit = models.IntegerField(default=60, help_text="제한 시간 (초)")
    triggered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-triggered_at']

    def __str__(self):
        return f"[Quiz #{self.id}] {self.question_text[:40]}..."


class LiveQuizResponse(models.Model):
    """
    학생의 라이브 퀴즈 응답.
    unique_together로 동일 퀴즈 중복 제출 방지.
    """
    quiz = models.ForeignKey(LiveQuiz, on_delete=models.CASCADE, related_name='responses')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='live_quiz_responses')
    answer = models.CharField(max_length=255)
    is_correct = models.BooleanField()
    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        unique_together = ['quiz', 'student']

    def __str__(self):
        return f"{self.student.username}: {'✅' if self.is_correct else '❌'} @ Quiz #{self.quiz_id}"


class LiveQuestion(models.Model):
    """
    라이브 세션 중 학생이 챗봇에 입력한 질문.
    자동으로 교수자 대시보드에 익명 전달된다.
    AI 답변은 즉시, 교수자 답변은 후속으로 제공.
    """
    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='questions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='live_questions')
    question_text = models.TextField()
    ai_answer = models.TextField(blank=True, help_text="RAG AI가 즉시 생성한 답변")
    instructor_answer = models.TextField(blank=True, help_text="교수자가 수동으로 작성한 답변")
    upvotes = models.IntegerField(default=0, help_text="다른 학생들의 공감 수")
    cluster_id = models.IntegerField(null=True, blank=True, help_text="유사 질문 그룹 ID")
    is_answered = models.BooleanField(default=False, help_text="교수자가 답변 완료 여부")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-upvotes', '-created_at']

    def __str__(self):
        return f"[Q] {self.question_text[:40]}... ({self.upvotes}👍)"


class LiveSessionNote(models.Model):
    """
    라이브 세션 종료 후 AI가 생성하는 통합 노트.
    STT + 퀴즈 결과 + Q&A + 이해도 데이터를 포함.
    """
    STATUS_CHOICES = (
        ('PENDING', '생성 중'),
        ('DONE', '완료'),
        ('FAILED', '실패'),
    )

    live_session = models.OneToOneField(LiveSession, on_delete=models.CASCADE, related_name='note')
    content = models.TextField(blank=True, help_text="AI 생성 통합 노트 (Markdown)")
    instructor_insight = models.TextField(blank=True, help_text="교수자용 인사이트 리포트 (Markdown)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    stats = models.JSONField(default=dict, help_text="세션 통계 (참가자수, 정답률 등)")
    # Step E: 승인 + 교안 매핑
    is_approved = models.BooleanField(default=False, help_text="교수자 승인 여부 (True=학생 공개)")
    approved_at = models.DateTimeField(null=True, blank=True)
    linked_materials = models.ManyToManyField('LectureMaterial', blank=True, related_name='linked_notes', help_text="세션에 연결된 교안")
    is_public = models.BooleanField(default=False, help_text="결석생 포함 전체 공개 여부")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'

    def __str__(self):
        return f"[Note] {self.live_session.session_code} ({self.status})"


# ══════════════════════════════════════════════════════════
# Phase 2-1: Weak Zone Alert
# ══════════════════════════════════════════════════════════

class WeakZoneAlert(models.Model):
    """학습자의 취약 구간 감지 기록"""
    TRIGGER_CHOICES = (
        ('QUIZ_WRONG', '퀴즈 오답'),
        ('PULSE_CONFUSED', '연속 혼란 펄스'),
        ('COMBINED', '복합 (오답+혼란)'),
    )
    STATUS_CHOICES = (
        ('DETECTED', '감지됨'),
        ('MATERIAL_PUSHED', '보충 자료 전송됨'),
        ('DISMISSED', '교수자 거부'),
        ('RESOLVED', '학생 확인'),
    )

    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='weak_zones')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='weak_zone_alerts')
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    trigger_detail = models.JSONField(default=dict, help_text="트리거 상세 { quiz_ids, confused_count, recent_topic }")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DETECTED')
    supplement_material = models.ForeignKey(LectureMaterial, on_delete=models.SET_NULL, null=True, blank=True, help_text="교수자가 푸시한 보충 자료")
    ai_suggested_content = models.TextField(blank=True, help_text="AI가 생성한 보충 설명")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-created_at']

    def __str__(self):
        return f"[WZ] {self.student.username}: {self.trigger_type} @ {self.live_session.session_code}"
