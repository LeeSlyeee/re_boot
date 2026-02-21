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
