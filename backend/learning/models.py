from django.db import models
from django.conf import settings
from courses.models import CourseSection


import random
import string

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

    def __str__(self):
        return f"[{self.access_code}] {self.title}"

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

    def __str__(self):
        return f"{self.student.username} - {self.section.title} ({self.session_order}교시)"

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
    section = models.ForeignKey(CourseSection, on_delete=models.CASCADE)
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

class AttemptDetail(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='details')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    student_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField()
