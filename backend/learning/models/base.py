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
    CATEGORY_CHOICES = (
        # ── IT 기술 스택 ──
        ('IT_FRONTEND', 'IT - 프론트엔드'),
        ('IT_BACKEND', 'IT - 백엔드'),
        ('IT_DB', 'IT - DB/ORM/캐시'),
        ('IT_DEVOPS', 'IT - 인프라/DevOps'),
        ('IT_TESTING', 'IT - 테스팅'),
        ('IT_RUNTIME', 'IT - 런타임'),
        ('IT_BUILD', 'IT - 빌드도구/CSS'),
        ('IT_SECURITY', 'IT - 보안'),
        ('IT_BAAS', 'IT - BaaS'),
        ('IT_GENERAL', 'IT - 종합'),
        # ── 교육공학 ──
        ('EDU_THEORY', '교육공학 - 학습이론'),
        ('EDU_DESIGN', '교육공학 - 교수설계'),
        ('EDU_TECH', '교육공학 - 에듀테크'),
        ('EDU_ASSESS', '교육공학 - 교육평가'),
        ('EDU_AI', '교육공학 - AI in Education'),
        ('EDU_LEARN_SCI', '교육공학 - 학습과학'),
        ('EDU_METHOD', '교육공학 - 교수학습방법'),
        ('EDU_GENERAL', '교육공학 - 종합'),
        # ── 기타 ──
        ('OTHER', '기타'),
    )

    title = models.CharField(max_length=200, help_text="클래스/강의명")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER', help_text="강의 분야 카테고리")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teaching_lectures')
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='enrolled_lectures', blank=True)
    access_code = models.CharField(max_length=6, unique=True, blank=True, help_text="수강생 입장 코드")
    start_date = models.DateField(null=True, blank=True, help_text="첫 강의일")
    end_date = models.DateField(null=True, blank=True, help_text="종강일")
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
    # [3-2] 강의 자료 파일 첨부
    file = models.FileField(upload_to='syllabus_files/', null=True, blank=True, help_text="강의 자료 첨부 파일")

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


class LectureNote(models.Model):
    """
    AI 요약 노트 (ERD: LectureNote)
    강의별 AI 생성 요약본 + 핵심 키워드.
    """
    lecture = models.ForeignKey(
        Lecture, on_delete=models.CASCADE, related_name='notes'
    )
    summary_content = models.TextField(help_text="AI 요약 노트")
    key_concepts = models.JSONField(
        default=list, blank=True,
        help_text="추출된 핵심 키워드 (예: ['클로저', 'this 바인딩', '프로토타입'])"
    )
    source_session = models.ForeignKey(
        'LearningSession', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lecture_notes',
        help_text="요약 생성에 사용된 세션"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-created_at']

    def __str__(self):
        return f"[Note] {self.lecture.title[:30]} — {len(self.key_concepts)}개 키워드"
