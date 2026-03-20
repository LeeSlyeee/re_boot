from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        INSTRUCTOR = 'INSTRUCTOR', 'Instructor'
        MANAGER = 'MANAGER', 'Manager'
    
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    
    # 추가 프로필 정보 (선택사항)
    goal_type = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. 취업, 창업")


class UserProfile(models.Model):
    """
    사용자 프로필 (ERD: UserProfile)
    학습 스타일, 관심사, 커리어 목표 등 상세 프로필 정보
    """
    CAREER_GOAL_CHOICES = (
        ('JOB_SEEKER', '취업 준비'),
        ('ENTREPRENEUR', '창업 준비'),
        ('SKILL_UP', '역량 강화'),
        ('CAREER_CHANGE', '직무 전환'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    career_goal = models.CharField(
        max_length=20, choices=CAREER_GOAL_CHOICES,
        blank=True, default='', help_text="커리어 목표"
    )
    preferred_tech_stack = models.JSONField(
        default=list, blank=True,
        help_text="관심 기술 스택 (예: ['React', 'Django', 'Docker'])"
    )
    learning_style = models.CharField(
        max_length=50, blank=True, default='',
        help_text="학습 스타일 (예: visual, auditory, reading, kinesthetic)"
    )
    preferences = models.JSONField(
        default=dict, blank=True,
        help_text="기타 학습 설정 (알림, 난이도 선호도 등)"
    )
    bio = models.TextField(blank=True, default='', help_text="자기소개")
    github_url = models.URLField(blank=True, default='', help_text="GitHub 프로필 URL")
    portfolio_url = models.URLField(blank=True, default='', help_text="포트폴리오 URL")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[Profile] {self.user.username} ({self.career_goal})"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """User 생성 시 UserProfile 자동 생성"""
    if created:
        UserProfile.objects.get_or_create(user=instance)


class ClassGroup(models.Model):
    name = models.CharField(max_length=100)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_classes')
    start_date = models.DateField()
    end_date = models.DateField()
    
    def __str__(self):
        return self.name

class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE, related_name='enrollments')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'class_group')
