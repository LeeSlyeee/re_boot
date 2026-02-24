from django.db import models
from django.conf import settings


class Course(models.Model):
    """
    강좌 모델 (ERD: Course)
    여러 Lecture를 묶는 상위 단위.
    """
    CATEGORY_CHOICES = (
        ('FRONTEND', '프론트엔드'),
        ('BACKEND', '백엔드'),
        ('FULLSTACK', '풀스택'),
        ('DATA', '데이터/AI'),
        ('DEVOPS', 'DevOps'),
        ('MOBILE', '모바일'),
        ('OTHER', '기타'),
    )

    title = models.CharField(max_length=200, help_text="강좌명")
    description = models.TextField(blank=True, help_text="강좌 설명")
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES,
        default='FULLSTACK', help_text="카테고리"
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='courses',
        help_text="강사"
    )
    is_active = models.BooleanField(default=True, help_text="활성 여부")
    thumbnail_url = models.URLField(blank=True, default='', help_text="썸네일 이미지 URL")
    estimated_weeks = models.IntegerField(default=12, help_text="예상 학습 기간 (주)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"


class CourseSection(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE,
        null=True, blank=True, related_name='sections',
        help_text="소속 강좌"
    )
    title = models.CharField(max_length=200)
    day_sequence = models.IntegerField(help_text="1일차, 2일차...")
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['day_sequence']

    def __str__(self):
        return f"Day {self.day_sequence}: {self.title}"
