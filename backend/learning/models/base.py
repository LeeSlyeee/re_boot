"""
학습 기본 모델: 강의, 실라버스, 학습 목표, 체크리스트
"""
from django.db import models
from django.conf import settings
from pgvector.django import VectorField
import random
import string


class VectorStore(models.Model):
    """
    RAG (Retrieval-Augmented Generation)를 위한 벡터 저장소
    강의 내용, 요약본 등을 청크(Chunk) 단위로 저장하고 임베딩 벡터를 함께 보관합니다.
    """
    content = models.TextField(help_text="원본 텍스트 청크")
    embedding = VectorField(dimensions=1536, help_text="OpenAI text-embedding-3-small (1536 dim)")

    # 메타데이터 (필터링용)
    session = models.ForeignKey('LearningSession', on_delete=models.CASCADE, null=True, blank=True, related_name='vectors')
    lecture = models.ForeignKey('Lecture', on_delete=models.CASCADE, null=True, blank=True, related_name='vectors')
    source_type = models.CharField(max_length=50, default='stt', help_text="stt, summary, material")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        indexes = [
            # HNSW 인덱스 (빠른 검색) - vector_cosine_ops 사용
            # Django 5.0+ 부터는 GinIndex 등을 지원하지만 pgvector 전용 인덱스는
            # RunSQL 등을 통해 생성하거나 pgvector 라이브러리 지원 확인 필요.
            # 우선 기본적으로 모델 정의만 하고,
            # 마이그레이션 시 CREATE INDEX 구문을 추가하는 것이 안전함.
        ]

    def __str__(self):
        return f"[{self.source_type}] {self.content[:30]}..."


class Lecture(models.Model):
    title = models.CharField(max_length=200, help_text="클래스/강의명")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teaching_lectures')
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='enrolled_lectures', blank=True)
    access_code = models.CharField(max_length=6, unique=True, blank=True, help_text="수강생 입장 코드")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'

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
        return code

    def __str__(self):
        return f"[{self.access_code}] {self.title}"


class Syllabus(models.Model):
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='syllabi')
    week_number = models.IntegerField(help_text="주차 (1, 2, ...)")
    title = models.CharField(max_length=200, help_text="주차별 주제")
    description = models.TextField(blank=True, help_text="주차 설명")

    class Meta:
        app_label = 'learning'
        ordering = ['week_number']
        unique_together = ['lecture', 'week_number']

    def __str__(self):
        return f"{self.lecture.title} - Week {self.week_number}: {self.title}"


class LearningObjective(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='objectives')
    content = models.CharField(max_length=300, help_text="학습 목표/체크리스트 항목")
    order = models.IntegerField(default=0, help_text="정렬 순서")

    class Meta:
        app_label = 'learning'
        ordering = ['order']

    def __str__(self):
        return f"[{self.syllabus.week_number}주차] {self.content}"


class StudentChecklist(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='checklists')
    objective = models.ForeignKey(LearningObjective, on_delete=models.CASCADE, related_name='student_checks')
    is_checked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'learning'
        unique_together = ['student', 'objective']
