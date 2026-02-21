"""
적응형/복습/형성평가 모델: AdaptiveContent, ReviewRoute, SpacedRepetitionItem,
FormativeAssessment, FormativeResponse
"""
from django.db import models
from django.conf import settings
from .live import LiveSession, LectureMaterial, LiveSessionNote, LiveQuiz


# ══════════════════════════════════════════════════════════
# Phase 2-2: 수준별 콘텐츠 분기
# ══════════════════════════════════════════════════════════

class AdaptiveContent(models.Model):
    """레벨별 AI 변형 교안"""
    LEVEL_CHOICES = ((1, 'Level 1 - 기초'), (2, 'Level 2 - 표준'), (3, 'Level 3 - 심화'))
    STATUS_CHOICES = (
        ('GENERATING', 'AI 생성 중'),
        ('DRAFT', 'AI 생성 초안'),
        ('APPROVED', '교수자 승인'),
        ('REJECTED', '교수자 거부'),
    )

    source_material = models.ForeignKey(LectureMaterial, on_delete=models.CASCADE, related_name='adaptive_contents')
    level = models.IntegerField(choices=LEVEL_CHOICES)
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="AI 변형 마크다운")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='GENERATING')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'learning'
        unique_together = ['source_material', 'level']
        ordering = ['level']

    def __str__(self):
        return f"[Adaptive L{self.level}] {self.source_material.title}"


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
        app_label = 'learning'
        unique_together = ['live_session', 'student']
        ordering = ['-created_at']

    def __str__(self):
        return f"[Review] {self.student.username} @ {self.live_session.session_code}"


class SpacedRepetitionItem(models.Model):
    """에빙하우스 5주기 간격 반복 스케줄"""
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spaced_items')
    concept_name = models.CharField(max_length=200, help_text="복습 개념명")
    source_session = models.ForeignKey(LiveSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='spaced_items')
    source_quiz = models.ForeignKey(LiveQuiz, on_delete=models.SET_NULL, null=True, blank=True)
    review_question = models.TextField(help_text="빠른 확인용 1문항")
    review_answer = models.CharField(max_length=500)
    review_options = models.JSONField(default=list, help_text="4지선다 보기")
    schedule = models.JSONField(default=list, help_text="5주기 스케줄 [{ review_num, label, due_at, completed }]")
    current_review = models.IntegerField(default=0, help_text="현재 몇 차 복습까지 완료")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
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
        app_label = 'learning'
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
        app_label = 'learning'
        unique_together = ['assessment', 'student']
        ordering = ['-submitted_at']

    def __str__(self):
        return f"[FR] {self.student.username}: {self.score}/{self.total}"
