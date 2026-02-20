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
        ordering = ['-created_at']

    def __str__(self):
        return f"[WZ] {self.student.username}: {self.trigger_type} @ {self.live_session.session_code}"

# ══════════════════════════════════════════════════════════
# Phase 2-3: AI 복습 루트 + 간격 반복
# ══════════════════════════════════════════════════════════

class ReviewRoute(models.Model):
    """세션별 학생 맞춤 AI 복습 루트"""
    STATUS_CHOICES = (
        ('SUGGESTED', 'AI 제안'),
        ('AUTO_APPROVED', '자동 승인'),
        ('APPROVED', '교수자 수동 승인'),
        ('MODIFIED', '교수자 수정'),
        ('REJECTED', '교수자 거부'),
    )

    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='review_routes')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_routes')
    items = models.JSONField(default=list, help_text="복습 항목 [{ order, type, title, content/note_id, est_minutes }]")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AUTO_APPROVED')
    total_est_minutes = models.IntegerField(default=0)
    completed_items = models.JSONField(default=list, help_text="완료된 order 목록 [1, 2, ...]")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['live_session', 'student']
        ordering = ['-created_at']

    def __str__(self):
        return f"[Review] {self.student.username} @ {self.live_session.session_code}"


class SpacedRepetitionItem(models.Model):
    """에빙하우스 5주기 간격 반복 스케줄"""
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spaced_items')
    concept_name = models.CharField(max_length=200, help_text="복습 개념명")
    source_session = models.ForeignKey(LiveSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='spaced_items')
    source_quiz = models.ForeignKey('LiveQuiz', on_delete=models.SET_NULL, null=True, blank=True)
    review_question = models.TextField(help_text="빠른 확인용 1문항")
    review_answer = models.CharField(max_length=500)
    review_options = models.JSONField(default=list, help_text="4지선다 보기")
    schedule = models.JSONField(default=list, help_text="5주기 스케줄 [{ review_num, label, due_at, completed }]")
    current_review = models.IntegerField(default=0, help_text="현재 몇 차 복습까지 완료")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[SR] {self.student.username}: {self.concept_name}"


# ══════════════════════════════════════════════════════════
# Phase 2-4: 사후 형성평가
# ══════════════════════════════════════════════════════════

class FormativeAssessment(models.Model):
    """세션 이후 AI가 노트 기반으로 생성하는 형성평가"""
    STATUS_CHOICES = (
        ('GENERATING', '생성 중'),
        ('READY', '준비 완료'),
        ('FAILED', '생성 실패'),
    )

    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='formative_assessments')
    note = models.ForeignKey(LiveSessionNote, on_delete=models.CASCADE, related_name='formative_assessments')
    questions = models.JSONField(default=list, help_text="""
    [{
        "id": 1,
        "question": "클로저란 무엇인가?",
        "options": ["A", "B", "C", "D"],
        "correct_answer": "B",
        "explanation": "...",
        "related_note_section": "## 핵심 내용 정리 > 1. 클로저",
        "concept_tag": "클로저"
    }]
    """)
    total_questions = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='GENERATING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[FA] {self.live_session.session_code} ({self.status})"


class FormativeResponse(models.Model):
    """학생의 형성평가 응답"""
    assessment = models.ForeignKey(FormativeAssessment, on_delete=models.CASCADE, related_name='responses')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='formative_responses')
    answers = models.JSONField(default=list, help_text="[{ question_id, answer, is_correct }]")
    score = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    sr_items_created = models.BooleanField(default=False, help_text="오답→SR 자동 등록 완료 여부")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['assessment', 'student']
        ordering = ['-submitted_at']

    def __str__(self):
        return f"[FR] {self.student.username}: {self.score}/{self.total}"


# ══════════════════════════════════════════════════════════
# Phase 1: 수준 진단 + 갭 맵
# ══════════════════════════════════════════════════════════

class Skill(models.Model):
    """
    역량 항목 (예: 클로저 이해, 비동기 처리, DOM 조작 등)
    갭 맵의 기본 블록 단위.
    """
    CATEGORY_CHOICES = (
        ('JAVASCRIPT', 'JavaScript'),
        ('PYTHON', 'Python'),
        ('HTML_CSS', 'HTML/CSS'),
        ('FRAMEWORK', 'Framework'),
        ('DATABASE', 'Database'),
        ('DEVOPS', 'DevOps'),
        ('CS_BASIC', 'CS 기초'),
        ('SOFT_SKILL', '소프트스킬'),
    )

    name = models.CharField(max_length=100, help_text="역량 이름 (예: 클로저 이해)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='JAVASCRIPT')
    description = models.TextField(blank=True, help_text="역량 상세 설명")
    difficulty_level = models.IntegerField(default=1, help_text="난이도 (1=기초, 2=중급, 3=심화)")
    order = models.IntegerField(default=0, help_text="표시 순서")

    class Meta:
        ordering = ['category', 'order']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name} (Lv{self.difficulty_level})"


class CareerGoal(models.Model):
    """
    직무/직종 목표 (예: 프론트엔드 개발자, 백엔드 개발자 등)
    각 목표에 필요한 역량(Skill)을 M2M으로 연결.
    """
    title = models.CharField(max_length=100, help_text="직무명 (예: 프론트엔드 개발자)")
    description = models.TextField(blank=True, help_text="직무 설명")
    required_skills = models.ManyToManyField(Skill, related_name='career_goals', blank=True)
    estimated_weeks = models.IntegerField(default=12, help_text="예상 학습 기간 (주)")
    icon = models.CharField(max_length=10, default='💻', help_text="아이콘 이모지")

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.icon} {self.title}"


class PlacementQuestion(models.Model):
    """
    입학 진단 테스트 문항.
    category로 개념 이해도/실습 경험/학습 패턴 구분.
    """
    CATEGORY_CHOICES = (
        ('CONCEPT', '개념 이해도'),
        ('PRACTICE', '실습 경험'),
        ('PATTERN', '학습 패턴'),
    )

    question_text = models.TextField(help_text="문제 내용")
    options = models.JSONField(help_text="보기 리스트 (예: ['A답', 'B답', 'C답', 'D답'])")
    correct_answer = models.CharField(max_length=255, help_text="정답")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='CONCEPT')
    difficulty = models.IntegerField(default=1, help_text="난이도 1~3")
    order = models.IntegerField(default=0, help_text="출제 순서")
    explanation = models.TextField(blank=True, help_text="정답 해설")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"[Q{self.order}] {self.question_text[:40]}..."


class PlacementResult(models.Model):
    """
    학생별 진단 결과.
    Level 1~3으로 분류.
    """
    LEVEL_CHOICES = (
        (1, 'Level 1: 완전 초보'),
        (2, 'Level 2: 기초 이해자'),
        (3, 'Level 3: 실습 경험자'),
    )

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='placement_results')
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='placement_results', null=True, blank=True)
    level = models.IntegerField(choices=LEVEL_CHOICES, default=1)
    score = models.IntegerField(default=0, help_text="총 맞은 개수")
    total_questions = models.IntegerField(default=20)
    answers = models.JSONField(default=dict, help_text="응답 기록 {question_id: selected_answer}")
    category_scores = models.JSONField(default=dict, help_text="카테고리별 점수 {CONCEPT: 5, PRACTICE: 3, PATTERN: 2}")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.username} → Level {self.level} ({self.score}/{self.total_questions})"


class StudentGoal(models.Model):
    """
    학생이 선택한 목표 직무.
    """
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_goals')
    career_goal = models.ForeignKey(CareerGoal, on_delete=models.CASCADE, related_name='students', null=True, blank=True)
    custom_goal_text = models.TextField(blank=True, help_text="직접 입력한 목표 (선택)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        if self.career_goal:
            return f"{self.student.username} → {self.career_goal.title}"
        return f"{self.student.username} → {self.custom_goal_text[:30]}"


class StudentSkill(models.Model):
    """
    학생별 역량 보유 상태 (갭 맵의 각 블록).
    세션 퀴즈 통과, 진단 결과 등으로 자동 업데이트.
    """
    STATUS_CHOICES = (
        ('OWNED', '보유 ✅'),
        ('GAP', '미보유 🔲'),
        ('LEARNING', '학습 중 🔄'),
    )

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='student_records')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='GAP')
    progress = models.IntegerField(default=0, help_text="숙달도 0~100%")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'skill']
        ordering = ['skill__category', 'skill__order']

    def __str__(self):
        return f"{self.student.username} | {self.skill.name} → {self.status} ({self.progress}%)"
