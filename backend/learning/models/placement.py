"""
수준 진단 및 갭 맵 모델: Skill, CareerGoal, PlacementQuestion, PlacementResult,
StudentGoal, StudentSkill, SkillBlock
"""
from django.db import models
from django.conf import settings
from .base import Lecture
from .live import LiveSession


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
        app_label = 'learning'
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
        app_label = 'learning'
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
        app_label = 'learning'
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
        app_label = 'learning'
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
        app_label = 'learning'
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
        app_label = 'learning'
        unique_together = ['student', 'skill']
        ordering = ['skill__category', 'skill__order']

    def __str__(self):
        return f"{self.student.username} | {self.skill.name} → {self.status} ({self.progress}%)"


# ══════════════════════════════════════════════════════════
# 스킬블록 시스템 (Phase 3 이후)
# ══════════════════════════════════════════════════════════

class SkillBlock(models.Model):
    """
    스킬블록 — 학습자가 획득한 시각적 역량 자산
    체크포인트 통과 + 이해도 + 형성평가 기반 자동 생성
    """
    LEVEL_EMOJIS = {1: '🌱', 2: '🌿', 3: '🌸'}

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skill_blocks')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='blocks')
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='skill_blocks')

    level = models.IntegerField(default=1, help_text="획득 시점 레벨 (1=Beginner/씨앗, 2=Intermediate/새싹, 3=Advanced/꽃)")
    checkpoint_score = models.FloatField(default=0, help_text="체크포인트 통과율 (0~100)")
    formative_score = models.FloatField(default=0, help_text="형성평가 점수 (0~100)")
    understand_score = models.FloatField(default=0, help_text="펄스 이해도 비율 (0~100)")
    total_score = models.FloatField(default=0, help_text="종합 점수 (가중 평균)")

    is_earned = models.BooleanField(default=False, help_text="블록 획득 여부")
    earned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        unique_together = ['student', 'skill', 'lecture']
        ordering = ['skill__category', 'skill__order']

    @property
    def emoji(self):
        return self.LEVEL_EMOJIS.get(self.level, '🌱')

    def __str__(self):
        earned = '✅' if self.is_earned else '🔲'
        return f"{earned} {self.emoji} {self.skill.name} ({self.total_score:.0f}점)"
