"""
AI 튜터 챗봇 모델: AIChatSession, AIChatMessage
동적 커리큘럼 리라우팅 모델: Curriculum, CurriculumItem, ReroutingLog
"""
from django.db import models
from django.conf import settings
from .base import Lecture


# ══════════════════════════════════════════════════════════
# AI 튜터 챗봇 (ERD: AIChatSession, AIChatMessage)
# ══════════════════════════════════════════════════════════

class AIChatSession(models.Model):
    """
    AI 튜터 채팅 세션.
    학생이 특정 강의 context에서 질문하면 RAG를 통해 공식 문서 기반 답변을 제공.
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='chat_sessions'
    )
    lecture = models.ForeignKey(
        Lecture, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='chat_sessions',
        help_text="질문 문맥 (어느 강의에서 질문했는지)"
    )
    title = models.CharField(
        max_length=200, blank=True, default='',
        help_text="세션 제목 (첫 질문에서 자동 생성)"
    )
    is_active = models.BooleanField(default=True, help_text="세션 활성 여부")
    start_time = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-updated_at']

    def __str__(self):
        lecture_name = self.lecture.title[:20] if self.lecture else '일반'
        return f"[Chat] {self.student.username} → {lecture_name}"


class AIChatMessage(models.Model):
    """AI 튜터 채팅 메시지"""
    SENDER_CHOICES = (
        ('USER', '학생'),
        ('AI', 'AI 튜터'),
        ('SYSTEM', '시스템'),
    )

    session = models.ForeignKey(
        AIChatSession, on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField(help_text="대화 내용")
    sources = models.JSONField(
        default=list, blank=True,
        help_text="RAG 참조 소스 [{title, url, similarity}]"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.sender}] {self.message[:40]}..."


# ══════════════════════════════════════════════════════════
# 동적 커리큘럼 리라우팅 (ERD: Curriculum, CurriculumItem, ReroutingLog)
# ══════════════════════════════════════════════════════════

class Curriculum(models.Model):
    """
    학생별 커리큘럼 (학습 경로).
    퀴즈 성적/진도에 따라 AI가 자동으로 경로를 재설계(Rerouting)함.
    """
    STATUS_CHOICES = (
        ('ACTIVE', '학습 중'),
        ('COMPLETED', '완료'),
        ('DROPPED', '중단'),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='curricula'
    )
    course_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="연결된 강좌명 (없으면 커스텀 커리큘럼)"
    )
    title = models.CharField(max_length=200, default='나의 학습 경로')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    start_date = models.DateField(auto_now_add=True)
    target_date = models.DateField(null=True, blank=True, help_text="목표 완료일")
    progress_percent = models.IntegerField(default=0, help_text="전체 진도율 (0~100)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-updated_at']

    def __str__(self):
        return f"[Curriculum] {self.student.username} — {self.title} ({self.status})"

    def update_progress(self):
        """아이템 완료율 기반으로 진도율 자동 계산"""
        total = self.items.count()
        if total == 0:
            self.progress_percent = 0
        else:
            completed = self.items.filter(is_completed=True).count()
            self.progress_percent = int((completed / total) * 100)
        self.save(update_fields=['progress_percent', 'updated_at'])


class CurriculumItem(models.Model):
    """커리큘럼 내 개별 학습 항목 (순서 조절 가능)"""
    TYPE_CHOICES = (
        ('LECTURE', '강의'),
        ('QUIZ', '퀴즈'),
        ('PROJECT', '프로젝트'),
        ('REVIEW', '복습'),
        ('SUPPLEMENT', '보충 학습'),
    )

    curriculum = models.ForeignKey(
        Curriculum, on_delete=models.CASCADE,
        related_name='items'
    )
    lecture = models.ForeignKey(
        Lecture, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='curriculum_items',
        help_text="연결된 강의"
    )
    title = models.CharField(max_length=200, help_text="항목 제목")
    item_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='LECTURE')
    order_index = models.IntegerField(default=0, help_text="동적으로 조절 가능한 순서")
    is_completed = models.BooleanField(default=False)
    is_supplementary = models.BooleanField(
        default=False, help_text="리라우팅으로 추가된 보충 항목인지"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['order_index']

    def __str__(self):
        status = '✅' if self.is_completed else '🔲'
        return f"{status} [{self.item_type}] {self.title}"


class ReroutingLog(models.Model):
    """
    커리큘럼 리라우팅 이력.
    AI가 퀴즈 실패, 진도 지연 등을 감지하면 학습 경로를 재설계하고 이력을 기록.
    """
    REASON_CHOICES = (
        ('QUIZ_FAIL', '퀴즈 낙제'),
        ('SLOW_PROGRESS', '진도 지연'),
        ('LOW_UNDERSTANDING', '이해도 부족'),
        ('SKILL_GAP', '스킬 갭 감지'),
        ('STUDENT_REQUEST', '학생 요청'),
        ('INSTRUCTOR_ADJUST', '강사 조정'),
    )

    curriculum = models.ForeignKey(
        Curriculum, on_delete=models.CASCADE,
        related_name='rerouting_logs'
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    reason_detail = models.TextField(
        blank=True, help_text="상세 사유 (예: Quiz #3 40점, 배열 메서드 이해 부족)"
    )
    old_path = models.JSONField(
        default=list, help_text="변경 전 Lecture IDs"
    )
    new_path = models.JSONField(
        default=list, help_text="변경 후 Lecture IDs (보충 포함)"
    )
    items_added = models.IntegerField(
        default=0, help_text="추가된 항목 수"
    )
    items_removed = models.IntegerField(
        default=0, help_text="제거된 항목 수"
    )
    ai_recommendation = models.TextField(
        blank=True, help_text="AI의 리라우팅 근거 설명"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-created_at']

    def __str__(self):
        return f"[Reroute] {self.curriculum} — {self.get_reason_display()}"
