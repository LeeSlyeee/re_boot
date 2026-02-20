from django.db import models
from django.conf import settings
from django.utils import timezone
from courses.models import CourseSection
from pgvector.django import VectorField
import random
import string

class VectorStore(models.Model):
    """
    RAG (Retrieval-Augmented Generation)를 위한 벡터 저장소
    강의 내용, 요약본 등을 청크(Chunk) 단위로 저장하고 임베딩 벡터를 함께 보관합니다.
    """
    content = models.TextField(help_text="원본 텍스트 청크")
    embedding = VectorField(dimensions=1536, help_text="OpenAI text-embedding-3-small (1536 dim)")
    
    # 메타데이터 (필터링용)
    session = models.ForeignKey('LearningSession', on_delete=models.CASCADE, null=True, blank=True, related_name='vectors')
    lecture = models.ForeignKey('Lecture', on_delete=models.CASCADE, null=True, blank=True, related_name='vectors')
    source_type = models.CharField(max_length=50, default='stt', help_text="stt, summary, material")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # HNSW 인덱스 (빠른 검색) - vector_cosine_ops 사용
            # Django 5.0+ 부터는 GinIndex 등을 지원하지만 pgvector 전용 인덱스는 
            # RunSQL 등을 통해 생성하거나 pgvector 라이브러리 지원 확인 필요.
            # 우선 기본적으로 모델 정의만 하고, 
            # 마이그레이션 시 CREATE INDEX 구문을 추가하는 것이 안전함.
        ]

    def __str__(self):
        return f"[{self.source_type}] {self.content[:30]}..."

class Lecture(models.Model):
    title = models.CharField(max_length=200, help_text="클래스/강의명")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teaching_lectures')
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='enrolled_lectures', blank=True)
    access_code = models.CharField(max_length=6, unique=True, blank=True, help_text="수강생 입장 코드")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # 코드가 없으면 자동 생성
        if not self.access_code:
            self.access_code = self._generate_unique_code()
        super().save(*args, **kwargs)

    def _generate_unique_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(6))
            if not Lecture.objects.filter(access_code=code).exists():
                return code
        return code

    def __str__(self):
        return f"[{self.access_code}] {self.title}"

class Syllabus(models.Model):
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='syllabi')
    week_number = models.IntegerField(help_text="주차 (1, 2, ...)")
    title = models.CharField(max_length=200, help_text="주차별 주제")
    description = models.TextField(blank=True, help_text="주차 설명")
    
    class Meta:
        ordering = ['week_number']
        unique_together = ['lecture', 'week_number']

    def __str__(self):
        return f"{self.lecture.title} - Week {self.week_number}: {self.title}"

class LearningObjective(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='objectives')
    content = models.CharField(max_length=300, help_text="학습 목표/체크리스트 항목")
    order = models.IntegerField(default=0, help_text="정렬 순서")
    
    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"[{self.syllabus.week_number}주차] {self.content}"

class StudentChecklist(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='checklists')
    objective = models.ForeignKey(LearningObjective, on_delete=models.CASCADE, related_name='student_checks')
    is_checked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'objective']

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

    def __str__(self):
        title = self.section.title if self.section else "자율학습"
        return f"{self.student.username} - {title} ({self.session_order}교시)"

class STTLog(models.Model):
    session = models.ForeignKey(LearningSession, on_delete=models.CASCADE, related_name='stt_logs')
    sequence_order = models.IntegerField()
    text_chunk = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sequence_order']

class SessionSummary(models.Model):
    session = models.ForeignKey(LearningSession, on_delete=models.CASCADE, related_name='summaries')
    content_text = models.TextField(help_text="AI 요약본")
    raw_stt_link = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DailyQuiz(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_quizzes')
    section = models.ForeignKey(CourseSection, on_delete=models.CASCADE, null=True, blank=True)
    quiz_date = models.DateField(auto_now_add=True)
    total_score = models.IntegerField(default=0)
    is_passed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class QuizQuestion(models.Model):
    quiz = models.ForeignKey(DailyQuiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    options = models.JSONField(help_text="객관식 보기 리스트")
    correct_answer = models.CharField(max_length=255)
    explanation = models.TextField(blank=True)

class QuizAttempt(models.Model):
    quiz = models.ForeignKey(DailyQuiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.IntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    review_note = models.TextField(blank=True, help_text="AI 오답노트 및 학습 가이드")

class AttemptDetail(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='details')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    student_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField()


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
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.original_filename} ({self.lecture.title})"


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

    class Meta:
        ordering = ['-created_at']

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
        ordering = ['sequence_order']

    def __str__(self):
        return f"[{self.sequence_order}] {self.text_chunk[:30]}..."
