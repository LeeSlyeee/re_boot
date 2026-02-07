from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        INSTRUCTOR = 'INSTRUCTOR', 'Instructor'
        MANAGER = 'MANAGER', 'Manager'
    
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    
    # 추가 프로필 정보 (선택사항)
    goal_type = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. 취업, 창업")

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
