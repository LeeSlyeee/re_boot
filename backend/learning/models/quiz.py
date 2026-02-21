"""
퀴즈 및 평가 모델: DailyQuiz, QuizQuestion, QuizAttempt, AttemptDetail
"""
from django.db import models
from django.conf import settings
from courses.models import CourseSection


class DailyQuiz(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_quizzes')
    section = models.ForeignKey(CourseSection, on_delete=models.CASCADE, null=True, blank=True)
    quiz_date = models.DateField(auto_now_add=True)
    total_score = models.IntegerField(default=0)
    is_passed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(DailyQuiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    options = models.JSONField(help_text="객관식 보기 리스트")
    correct_answer = models.CharField(max_length=255)
    explanation = models.TextField(blank=True)

    class Meta:
        app_label = 'learning'


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(DailyQuiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.IntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    review_note = models.TextField(blank=True, help_text="AI 오답노트 및 학습 가이드")

    class Meta:
        app_label = 'learning'


class AttemptDetail(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='details')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    student_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField()

    class Meta:
        app_label = 'learning'
