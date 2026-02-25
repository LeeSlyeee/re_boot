"""
커리큘럼 리라우팅 API Views
============================
동적 학습 경로 관리 + AI 기반 자동 리라우팅

Endpoints:
  GET/POST /api/learning/curriculum/                    → 내 커리큘럼 목록/생성
  GET      /api/learning/curriculum/{id}/               → 커리큘럼 상세 (아이템 포함)
  POST     /api/learning/curriculum/{id}/complete_item/ → 항목 완료 처리
  POST     /api/learning/curriculum/{id}/reroute/       → AI 리라우팅 실행
  GET      /api/learning/curriculum/{id}/history/       → 리라우팅 이력 조회
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import models as db_models

import openai
import json
from django.conf import settings

from .models import (
    Curriculum, CurriculumItem, ReroutingLog,
    Lecture, QuizAttempt, SkillBlock,
)
from .serializers import (
    CurriculumSerializer,
    CurriculumDetailSerializer,
    CurriculumItemSerializer,
    ReroutingLogSerializer,
)


class CurriculumViewSet(viewsets.ModelViewSet):
    """커리큘럼 ViewSet"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CurriculumSerializer

    def get_queryset(self):
        return Curriculum.objects.filter(
            student=self.request.user
        ).prefetch_related('items', 'rerouting_logs')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CurriculumDetailSerializer
        return CurriculumSerializer

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        학생의 수강 강의 기반으로 AI가 맞춤형 커리큘럼을 자동 생성.
        POST /api/learning/curriculum/generate/
        """
        student = request.user

        # 이미 ACTIVE 커리큘럼이 있으면 중복 생성 방지
        existing = Curriculum.objects.filter(student=student, status='ACTIVE')
        if existing.exists():
            return Response(
                {'error': '이미 활성 커리큘럼이 존재합니다. 기존 커리큘럼을 완료/삭제 후 생성해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 수강 중인 강의 목록 수집
        enrolled_lectures = Lecture.objects.filter(students=student)
        lecture_info = "\n".join([
            f"- {lec.title} (강사: {lec.instructor.username if lec.instructor else '미정'})"
            for lec in enrolled_lectures
        ]) or "수강 중인 강의 없음 (일반 웹 개발 로드맵 생성)"

        # 기존 퀴즈/스킬블록 데이터
        quiz_attempts = QuizAttempt.objects.filter(student=student).order_by('-submitted_at')[:5]
        quiz_summary = "\n".join([
            f"- 퀴즈 #{a.quiz_id}: {a.score}점"
            for a in quiz_attempts
        ]) or "퀴즈 이력 없음"

        skill_blocks = SkillBlock.objects.filter(student=student)
        skill_summary = "\n".join([
            f"- {s.title}: {'획득' if s.is_earned else '미획득'}"
            for s in skill_blocks
        ]) or "스킬블록 없음"

        # AI 커리큘럼 생성
        curriculum_title = "나의 학습 로드맵"
        course_name = ""
        items_to_create = []

        if enrolled_lectures.exists():
            first_lecture = enrolled_lectures.first()
            curriculum_title = f"{first_lecture.title} 학습 로드맵"
            course_name = first_lecture.title

        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60.0)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """
너는 IT 부트캠프의 '학습 경로 설계 전문가'야.
학생의 수강 강의, 퀴즈 성적, 보유 스킬을 분석하여 최적의 학습 커리큘럼을 설계해줘.

[응답 규칙]
1. JSON 형식으로만 응답
2. 8~15개의 학습 항목을 순서대로 제안
3. 각 항목은 title, type(LECTURE/QUIZ/PROJECT/REVIEW), description을 포함
4. 한국어로 작성

[응답 형식]
{
  "title": "커리큘럼 제목",
  "items": [
    {"title": "항목 제목", "type": "LECTURE", "description": "간단 설명"},
    {"title": "중간 점검 퀴즈", "type": "QUIZ", "description": "학습 이해도 확인"}
  ]
}
                    """},
                    {"role": "user", "content": f"""
[수강 강의]:
{lecture_info}

[퀴즈 성적]:
{quiz_summary}

[보유 스킬]:
{skill_summary}

위 데이터를 기반으로 맞춤형 학습 커리큘럼을 설계해줘.
                    """}
                ],
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            ai_result = json.loads(response.choices[0].message.content)
            if ai_result.get('title'):
                curriculum_title = ai_result['title']
            items_to_create = ai_result.get('items', [])

        except Exception as e:
            # AI 실패 시 기본 항목으로 fallback
            items_to_create = [
                {"title": "오리엔테이션 & 환경 설정", "type": "LECTURE"},
                {"title": "기초 문법 학습", "type": "LECTURE"},
                {"title": "기초 확인 퀴즈", "type": "QUIZ"},
                {"title": "핵심 개념 심화", "type": "LECTURE"},
                {"title": "실습 프로젝트", "type": "PROJECT"},
                {"title": "중간 점검 퀴즈", "type": "QUIZ"},
                {"title": "응용 학습", "type": "LECTURE"},
                {"title": "종합 복습", "type": "REVIEW"},
                {"title": "최종 프로젝트", "type": "PROJECT"},
            ]

        # 커리큘럼 생성
        target_date = timezone.now().date() + timezone.timedelta(weeks=8)
        curriculum = Curriculum.objects.create(
            student=student,
            title=curriculum_title,
            course_name=course_name,
            target_date=target_date,
        )

        # 항목 생성 (수강 중인 첫 번째 강의와 연결)
        linked_lecture = enrolled_lectures.first() if enrolled_lectures.exists() else None
        for idx, item_data in enumerate(items_to_create):
            CurriculumItem.objects.create(
                curriculum=curriculum,
                title=item_data.get('title', f'학습 항목 {idx + 1}'),
                item_type=item_data.get('type', 'LECTURE'),
                order_index=idx + 1,
                lecture=linked_lecture,
            )

        return Response(
            CurriculumDetailSerializer(curriculum).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def complete_item(self, request, pk=None):
        """커리큘럼 항목 완료/해제 토글"""
        curriculum = self.get_object()
        item_id = request.data.get('item_id')

        try:
            item = CurriculumItem.objects.get(
                id=item_id, curriculum=curriculum
            )
        except CurriculumItem.DoesNotExist:
            return Response(
                {'error': '해당 항목을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 토글: 완료 ↔ 미완료
        item.is_completed = not item.is_completed
        item.completed_at = timezone.now() if item.is_completed else None
        item.save(update_fields=['is_completed', 'completed_at'])

        # 전체 진도율 업데이트
        curriculum.update_progress()

        # 완료율 100%면 커리큘럼 상태 변경, 아니면 ACTIVE로
        if curriculum.progress_percent >= 100:
            curriculum.status = 'COMPLETED'
        else:
            curriculum.status = 'ACTIVE'
        curriculum.save(update_fields=['status'])

        return Response({
            'item_id': item.id,
            'is_completed': item.is_completed,
            'progress_percent': curriculum.progress_percent,
            'curriculum_status': curriculum.status,
        })

    @action(detail=True, methods=['post'])
    def reroute(self, request, pk=None):
        """
        AI 기반 커리큘럼 리라우팅.
        퀴즈 성적, 진도, 이해도를 분석하여 학습 경로를 재설계.
        """
        curriculum = self.get_object()
        reason = request.data.get('reason', 'QUIZ_FAIL')
        reason_detail = request.data.get('reason_detail', '')

        # 현재 경로 스냅샷
        old_items = list(curriculum.items.values_list('id', flat=True))

        # 학생 학습 데이터 수집
        student = curriculum.student
        quiz_attempts = QuizAttempt.objects.filter(
            student=student
        ).order_by('-submitted_at')[:10]

        quiz_summary = "\n".join([
            f"- 퀴즈 #{a.quiz_id}: {a.score}점 ({'통과' if a.score >= 60 else '미통과'})"
            for a in quiz_attempts
        ]) or "퀴즈 이력 없음"

        skill_blocks = SkillBlock.objects.filter(
            student=student
        ).order_by('-created_at')[:10]
        skill_summary = "\n".join([
            f"- {s.title}: {'획득' if s.is_earned else '미획득'} ({s.level}레벨)"
            for s in skill_blocks
        ]) or "스킬블록 없음"

        # 현재 커리큘럼 상태
        current_items = curriculum.items.all()
        curriculum_text = "\n".join([
            f"- [{i.order_index}] {i.title} ({'✅' if i.is_completed else '🔲'}) [{i.item_type}]"
            for i in current_items
        ])

        # AI 리라우팅 추천
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """
너는 IT 부트캠프의 '학습 경로 설계 전문가'야.
학생의 퀴즈 성적, 스킬 보유 현황, 현재 진도를 분석하여 최적의 학습 경로를 재설계해줘.

[응답 규칙]
1. JSON 형식으로 응답할 것.
2. 추가할 보충 학습 항목과 순서 변경 사항을 제안할 것.
3. 한국어로 근거를 설명할 것.

[응답 형식]
{
  "recommendation": "리라우팅 근거 설명 (한국어)",
  "add_items": [
    {"title": "추가 항목 제목", "type": "SUPPLEMENT", "order": 5}
  ],
  "reorder": [
    {"item_title": "기존 항목", "new_order": 3}
  ]
}
                    """},
                    {"role": "user", "content": f"""
[리라우팅 사유]: {reason} - {reason_detail}

[퀴즈 성적]:
{quiz_summary}

[스킬 보유 현황]:
{skill_summary}

[현재 커리큘럼]:
{curriculum_text}

위 데이터를 분석하여 학습 경로 재설계를 제안해줘.
                    """}
                ],
                max_tokens=1000,
                response_format={"type": "json_object"},
            )

            ai_result = json.loads(response.choices[0].message.content)
            recommendation = ai_result.get('recommendation', '')
            add_items = ai_result.get('add_items', [])

            # 보충 항목 추가
            items_added = 0
            max_order = curriculum.items.aggregate(
                db_models.Max('order_index')
            )['order_index__max'] or 0

            for new_item in add_items:
                max_order += 1
                CurriculumItem.objects.create(
                    curriculum=curriculum,
                    title=new_item.get('title', '보충 학습'),
                    item_type=new_item.get('type', 'SUPPLEMENT'),
                    order_index=new_item.get('order', max_order),
                    is_supplementary=True,
                )
                items_added += 1

        except Exception as e:
            recommendation = f"AI 리라우팅 분석 실패: {str(e)}"
            items_added = 0

        # 새 경로 스냅샷
        new_items = list(curriculum.items.values_list('id', flat=True))

        # 리라우팅 로그 기록
        log = ReroutingLog.objects.create(
            curriculum=curriculum,
            reason=reason,
            reason_detail=reason_detail,
            old_path=old_items,
            new_path=new_items,
            items_added=items_added,
            items_removed=0,
            ai_recommendation=recommendation,
        )

        # 진도율 재계산
        curriculum.update_progress()

        return Response({
            'rerouting_id': log.id,
            'recommendation': recommendation,
            'items_added': items_added,
            'new_progress': curriculum.progress_percent,
            'curriculum': CurriculumDetailSerializer(curriculum).data,
        })

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """리라우팅 이력 조회"""
        curriculum = self.get_object()
        logs = ReroutingLog.objects.filter(curriculum=curriculum)
        serializer = ReroutingLogSerializer(logs, many=True)
        return Response(serializer.data)
