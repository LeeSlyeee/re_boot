"""
Phase 2-2: 적응형 콘텐츠 분기 API Views
"""
import os
import openai
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import AdaptiveContent, LectureMaterial, LiveSession, PlacementResult


class GenerateAdaptiveView(APIView):
    """POST /api/learning/materials/{id}/generate-adaptive/ — 3레벨 변형 생성"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        material = get_object_or_404(LectureMaterial, id=pk, uploaded_by=request.user)

        # 이미 생성되어 있으면 반환
        existing = AdaptiveContent.objects.filter(source_material=material)
        if existing.filter(status__in=['DRAFT', 'APPROVED']).count() >= 3:
            return Response({
                'message': '이미 3레벨 모두 생성되어 있습니다.',
                'levels': [{'id': a.id, 'level': a.level, 'status': a.status} for a in existing],
            })

        # 텍스트 추출
        source_text = self._extract_text(material)
        if not source_text:
            return Response({'error': '이 형식은 자동 변형이 지원되지 않습니다. 마크다운(MD) 파일을 사용해주세요.'},
                          status=status.HTTP_400_BAD_REQUEST)

        # 3레벨 변형 생성
        levels_config = {
            1: {
                'label': 'Level 1 - 기초',
                'prompt': '전문 용어를 쉬운 표현으로 변환하고, 비유와 일상 예시를 추가하세요. 핵심 3줄 요약을 끝에 추가하세요.',
            },
            2: {
                'label': 'Level 2 - 표준',
                'prompt': '원본 내용을 유지하되 핵심 부분을 강조(볼드)하고, 실습 문제 2~3개를 추가하세요.',
            },
            3: {
                'label': 'Level 3 - 심화',
                'prompt': '심화 개념과 이론적 배경을 추가하고, "더 나아가기" 확장 과제와 실무 사례를 포함하세요.',
            },
        }

        results = []
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        for level, config in levels_config.items():
            # 중복 방지
            if AdaptiveContent.objects.filter(source_material=material, level=level).exists():
                ac = AdaptiveContent.objects.get(source_material=material, level=level)
                results.append({'id': ac.id, 'level': level, 'status': ac.status})
                continue

            ac = AdaptiveContent.objects.create(
                source_material=material,
                level=level,
                title=f"{material.title} ({config['label']})",
                status='GENERATING',
            )

            try:
                response = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[
                        {'role': 'system', 'content': f"""당신은 교육 콘텐츠 전문가입니다.
아래 원본 교안을 **{config['label']}** 수준으로 변형해주세요.

규칙: {config['prompt']}

마크다운 형식으로 작성하세요."""},
                        {'role': 'user', 'content': f'원본 교안:\n\n{source_text[:3000]}'},
                    ],
                    temperature=0.5,
                    max_tokens=2000,
                )

                ac.content = response.choices[0].message.content.strip()
                ac.status = 'DRAFT'
                ac.save()
                results.append({'id': ac.id, 'level': level, 'status': 'DRAFT'})

            except Exception as e:
                ac.status = 'DRAFT'
                ac.content = f'[생성 실패: {str(e)}]'
                ac.save()
                results.append({'id': ac.id, 'level': level, 'status': 'DRAFT', 'error': str(e)})

        return Response({'levels': results}, status=status.HTTP_201_CREATED)

    def _extract_text(self, material):
        """교안 텍스트 추출 (1차: MD만 지원)"""
        if material.file_type == 'MD' and material.file:
            try:
                material.file.open('r')
                text = material.file.read()
                material.file.close()
                if isinstance(text, bytes):
                    text = text.decode('utf-8')
                return text
            except Exception:
                pass

        # PDF: PyMuPDF 시도
        if material.file_type == 'PDF' and material.file:
            try:
                import fitz
                doc = fitz.open(material.file.path)
                text = ''
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text if text.strip() else None
            except ImportError:
                pass

        # PPT: python-pptx 시도
        if material.file_type == 'PPT' and material.file:
            try:
                from pptx import Presentation
                prs = Presentation(material.file.path)
                text = ''
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, 'text'):
                            text += shape.text + '\n'
                return text if text.strip() else None
            except ImportError:
                pass

        return None


class ListAdaptiveView(APIView):
    """GET /api/learning/materials/{id}/adaptive/ — 교안의 레벨별 변형 목록"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        material = get_object_or_404(LectureMaterial, id=pk)
        contents = AdaptiveContent.objects.filter(source_material=material)

        data = [
            {
                'id': ac.id,
                'level': ac.level,
                'level_label': ac.get_level_display(),
                'title': ac.title,
                'content_preview': ac.content[:200] + '...' if len(ac.content) > 200 else ac.content,
                'status': ac.status,
                'created_at': ac.created_at,
            }
            for ac in contents
        ]
        return Response({'adaptive_contents': data})


class ApproveAdaptiveView(APIView):
    """POST /api/learning/adaptive/{id}/approve/ — 변형 승인"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ac = get_object_or_404(AdaptiveContent, id=pk, source_material__uploaded_by=request.user)
        ac.status = 'APPROVED'
        ac.approved_at = timezone.now()
        ac.save()
        return Response({'ok': True, 'status': 'APPROVED'})


class MyContentView(APIView):
    """GET /api/learning/live/{id}/my-content/ — 학생 레벨에 맞는 자료 조회"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        session = get_object_or_404(LiveSession, id=pk)

        # 학생 레벨 결정 (PlacementResult 기반)
        placement = PlacementResult.objects.filter(student=request.user).order_by('-created_at').first()
        level_map = {'BEGINNER': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}
        student_level = level_map.get(placement.level, 2) if placement else 2

        # 세션에 연결된 교안의 적응형 콘텐츠 조회
        materials = session.lecture.materials.all() if session.lecture else []
        my_contents = []

        for material in materials:
            # 내 레벨 콘텐츠 (승인된 것만)
            adaptive = AdaptiveContent.objects.filter(
                source_material=material,
                level=student_level,
                status='APPROVED',
            ).first()

            my_contents.append({
                'material_id': material.id,
                'material_title': material.title,
                'file_type': material.file_type,
                'adaptive_content': {
                    'id': adaptive.id,
                    'level': adaptive.level,
                    'level_label': adaptive.get_level_display(),
                    'title': adaptive.title,
                    'content': adaptive.content,
                } if adaptive else None,
                'original_url': material.file.url if material.file else '',
            })

        return Response({
            'student_level': student_level,
            'contents': my_contents,
        })
