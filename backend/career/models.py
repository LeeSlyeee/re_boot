from django.db import models
from django.conf import settings

class Portfolio(models.Model):
    TYPE_CHOICES = (
        ('JOB', '취업용 포트폴리오 (Job Portfolio)'),
        ('STARTUP', '창업용 MVP 기획서 (Startup MVP Spec)'),
    )
    
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='portfolios')
    portfolio_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200, default="자동 생성된 포트폴리오")
    content = models.TextField(help_text="Markdown 형식의 생성된 포트폴리오 내용")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_portfolio_type_display()}] {self.student.username} - {self.title}"

class MockInterview(models.Model):
    PERSONA_CHOICES = (
        ('TECH_LEAD', '깐깐한 기술 팀장'),
        ('FRIENDLY_SENIOR', '친절한 사수'),
        ('HR_MANAGER', '인사 담당자'),
        ('STARTUP_CEO', '스타트업 대표'),
        ('BIG_TECH', '글로벌 빅테크 면접관'),
        ('PRESSURE', '압박 면접관'),
        ('GROWTH', '성장 잠재력 평가관'),
        ('PEER', '동료 개발자'),
    )
    
    STATUS_CHOICES = (
        ('IN_PROGRESS', '면접 진행 중'),
        ('COMPLETED', '종료됨'),
    )
    
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interviews')
    portfolio = models.ForeignKey(Portfolio, on_delete=models.SET_NULL, null=True, related_name='interviews')
    persona = models.CharField(max_length=20, choices=PERSONA_CHOICES, default='TECH_LEAD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_PROGRESS')
    max_questions = models.IntegerField(null=True, blank=True, help_text="최대 질문 수 (null이면 무제한)")
    max_minutes = models.IntegerField(null=True, blank=True, help_text="최대 면접 시간(분) (null이면 무제한)")
    report_data = models.TextField(blank=True, default='', help_text="면접 결과 리포트 JSON")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"[{self.get_persona_display()}] {self.student.username}의 면접"

class InterviewExchange(models.Model):
    interview = models.ForeignKey(MockInterview, on_delete=models.CASCADE, related_name='exchanges')
    question = models.TextField(help_text="AI 질문")
    answer = models.TextField(blank=True, help_text="사용자 답변")
    feedback = models.TextField(blank=True, help_text="AI 피드백 및 평가")
    score = models.IntegerField(default=0, help_text="답변 점수 (0~100)")
    order = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order']


class PortfolioProject(models.Model):
    """
    포트폴리오 프로젝트 (ERD: PortfolioProject)
    스킬블록과 연결되어 해당 스킬의 근거 자료로 활용.
    """
    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name='projects'
    )
    skill_block_id = models.IntegerField(
        null=True, blank=True,
        help_text="관련 스킬블록 ID (learning.SkillBlock)"
    )
    name = models.CharField(max_length=200, help_text="프로젝트/기능 명")
    description = models.TextField(blank=True, help_text="프로젝트 설명")
    tech_stack = models.JSONField(
        default=list, blank=True,
        help_text="사용 기술 (예: ['React', 'Django', 'PostgreSQL'])"
    )
    github_url = models.URLField(blank=True, default='', help_text="GitHub 리포지토리 URL")
    demo_url = models.URLField(blank=True, default='', help_text="데모/배포 URL")
    role = models.CharField(
        max_length=100, blank=True, default='',
        help_text="담당 역할 (예: 프론트엔드 개발)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[Project] {self.name} → {self.portfolio.student.username}"


class InterviewPersona(models.Model):
    """
    면접 페르소나 (ERD: InterviewPersona)
    AI 면접관의 성격/역할/난이도를 사전 정의.
    MockInterview에서 persona FK로 참조.
    """
    ROLE_CHOICES = (
        ('TECH_LEAD', '기술 팀장'),
        ('HR', '인사 담당자'),
        ('VC', '벤처 캐피탈리스트'),
        ('PEER', '동료 개발자'),
        ('CUSTOMER', '고객'),
        ('STARTUP_CEO', '스타트업 대표'),
        ('BIG_TECH', '빅테크 면접관'),
    )
    DIFFICULTY_CHOICES = (
        ('EASY', '기본'),
        ('NORMAL', '보통'),
        ('HARD', '압박'),
    )

    name = models.CharField(max_length=100, help_text="페르소나 이름 (e.g. 까칠한 CTO)")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='TECH_LEAD')
    system_prompt = models.TextField(
        help_text="AI 페르소나 정의 프롬프트"
    )
    difficulty = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, default='NORMAL'
    )
    avatar_emoji = models.CharField(max_length=10, default='🤖', help_text="아바타 이모지")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['role', 'difficulty']

    def __str__(self):
        return f"[{self.role}] {self.name} ({self.get_difficulty_display()})"
