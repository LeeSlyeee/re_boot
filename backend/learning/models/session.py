"""
학습 세션 모델: 학습 세션, STT 로그, 세션 요약, 녹음 업로드
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from courses.models import CourseSection
from .base import Lecture


class LearningSession(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='learning_sessions')
    lecture = models.ForeignKey(Lecture, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    # course field removed temporarily to fix ImportError
    section = models.ForeignKey(CourseSection, on_delete=models.CASCADE, null=True, blank=True)
    session_date = models.DateField(auto_now_add=True)
    session_order = models.IntegerField(help_text="1교시, 2교시...")

    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    youtube_url = models.URLField(max_length=500, blank=True, null=True, help_text="유튜브 학습 시 영상 URL")

    # [New] 대화 압축 (Conversation Compression)
    context_summary = models.TextField(blank=True, null=True, help_text="현재까지의 대화/자막 압축 요약본")
    last_compressed_at = models.DateTimeField(default=timezone.now, help_text="마지막 압축 시점")

    class Meta:
        app_label = 'learning'

    def __str__(self):
        title = self.section.title if self.section else "자율학습"
        return f"{self.student.username} - {title} ({self.session_order}교시)"


class STTLog(models.Model):
    session = models.ForeignKey(LearningSession, on_delete=models.CASCADE, related_name='stt_logs')
    sequence_order = models.IntegerField()
    text_chunk = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['sequence_order']


class SessionSummary(models.Model):
    session = models.ForeignKey(LearningSession, on_delete=models.CASCADE, related_name='summaries')
    content_text = models.TextField(help_text="AI 요약본")
    raw_stt_link = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'


class RecordingUpload(models.Model):
    """
    강의 녹음 파일 업로드 → STT → 요약 가공 파이프라인 추적 모델
    1시간 강의 기준 설계 (약 50~100MB, mp3/m4a/wav)
    """
    STATUS_CHOICES = (
        ('PENDING', '대기 중'),
        ('SPLITTING', '오디오 분할 중'),
        ('TRANSCRIBING', 'STT 변환 중'),
        ('SUMMARIZING', '요약 생성 중'),
        ('COMPLETED', '완료'),
        ('FAILED', '실패'),
    )

    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='recordings')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey(
        LearningSession, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="처리 완료 후 연결되는 학습 세션"
    )

    # 파일 정보
    audio_file = models.FileField(upload_to='recordings/%Y/%m/')
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(default=0, help_text="바이트 단위")
    duration_seconds = models.IntegerField(null=True, blank=True, help_text="오디오 길이(초)")

    # 처리 상태
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    progress = models.IntegerField(default=0, help_text="처리 진행률 0~100")
    total_chunks = models.IntegerField(default=0, help_text="분할된 총 청크 수")
    processed_chunks = models.IntegerField(default=0, help_text="처리 완료된 청크 수")
    error_message = models.TextField(blank=True)

    # 타임스탬프
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.original_filename} ({self.lecture.title})"
