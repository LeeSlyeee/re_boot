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
