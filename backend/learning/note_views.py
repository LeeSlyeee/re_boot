"""
라이브 세션 노트 관련 Views: 노트 조회, 승인, 교안 연결, 결석 노트
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    LiveSession, LiveParticipant, LectureMaterial,
    LiveSessionNote, Lecture, NoteViewLog
)


class LiveNoteView(APIView):
    """
    GET /api/learning/live/{id}/note/
    통합 노트 조회 (교수자 + 참가자 모두)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        session = get_object_or_404(LiveSession, id=pk)

        # 권한: 교수자이거나 참가자
        is_instructor = session.instructor == request.user
        is_participant = session.participants.filter(student=request.user).exists()
        if not is_instructor and not is_participant:
            return Response({'error': '접근 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            note = session.note
        except LiveSessionNote.DoesNotExist:
            return Response({'error': '아직 노트가 생성되지 않았습니다.', 'status': 'NOT_STARTED'},
                            status=status.HTTP_404_NOT_FOUND)

        response_data = {
            'session_id': session.id,
            'status': note.status,
            'content': note.content if note.status == 'DONE' else '',
            'stats': note.stats,
            'created_at': note.created_at,
        }

        # 학생인 경우: 승인된 노트만 공개
        if not is_instructor and not note.is_approved:
            return Response({
                'session_id': session.id,
                'status': note.status,
                'content': '',
                'stats': note.stats,
                'is_approved': False,
                'message': '교수자가 아직 노트를 검토 중입니다.',
            })

        response_data['is_approved'] = note.is_approved
        response_data['is_public'] = note.is_public
        response_data['linked_materials'] = [
            {'id': m.id, 'title': m.title, 'file_type': m.file_type, 'file_url': m.file.url if m.file else ''}
            for m in note.linked_materials.all()
        ]

        # Phase 3: 학생이 노트를 조회하면 NoteViewLog 기록
        if not is_instructor:
            NoteViewLog.objects.get_or_create(note=note, student=request.user)

        # 교수자에게만 인사이트 리포트 제공
        if is_instructor:
            response_data['instructor_insight'] = note.instructor_insight or ''

        return Response(response_data)

    def patch(self, request, pk):
        """
        PATCH /api/learning/live/{id}/note/
        교수자: 노트 수정 (내용 편집)
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        try:
            note = session.note
        except LiveSessionNote.DoesNotExist:
            return Response({'error': '노트가 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        # Whitelist 방식: 허용된 필드만 수정
        if 'content' in request.data:
            note.content = request.data['content']
        note.save()
        return Response({'ok': True, 'message': '노트가 수정되었습니다.'})


class NoteApproveView(APIView):
    """
    POST /api/learning/live/{id}/note/approve/
    교수자가 노트를 검토 후 승인 → 학생에게 공개
    B4: 배포 범위(scope) 선택 지원
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        try:
            note = session.note
        except LiveSessionNote.DoesNotExist:
            return Response({'error': '노트가 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        note.is_approved = True
        note.approved_at = timezone.now()

        # B4: 배포 범위 선택
        # scope: 'ALL' (전체), 'ATTENDEES' (출석자만), 'ABSENT' (결석자만), 'LEVEL_1/2/3' (특정 레벨만)
        scope = request.data.get('scope', 'ALL')
        make_public = request.data.get('is_public', scope in ('ALL', 'ABSENT'))
        note.is_public = make_public

        # stats에 scope 정보 저장
        current_stats = note.stats or {}
        current_stats['distribution_scope'] = scope
        note.stats = current_stats
        note.save()

        return Response({
            'ok': True,
            'is_approved': True,
            'is_public': note.is_public,
            'scope': scope,
            'approved_at': note.approved_at,
        })


class NoteMaterialLinkView(APIView):
    """
    POST /api/learning/live/{id}/note/materials/
    교수자: 세션 노트에 교안 연결
    Body: { "material_ids": [1, 2, 3] }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        try:
            note = session.note
        except LiveSessionNote.DoesNotExist:
            return Response({'error': '노트가 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        material_ids = request.data.get('material_ids', [])
        materials = LectureMaterial.objects.filter(id__in=material_ids, lecture=session.lecture)
        note.linked_materials.set(materials)

        return Response({
            'ok': True,
            'linked_count': materials.count(),
            'materials': [
                {'id': m.id, 'title': m.title, 'file_type': m.file_type}
                for m in materials
            ],
        })


class AbsentNoteListView(APIView):
    """
    GET /api/learning/absent-notes/{lecture_id}/
    결석생용: 자신이 참여하지 않았지만 공개(is_public=True)된 세션 노트 목록
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id)

        # 자신이 참여한 세션 ID
        participated = LiveParticipant.objects.filter(
            student=request.user,
            live_session__lecture=lecture
        ).values_list('live_session_id', flat=True)

        # 참여하지 않은 + 공개된 노트
        absent_notes = LiveSessionNote.objects.filter(
            live_session__lecture=lecture,
            is_public=True,
            is_approved=True,
            status='DONE',
        ).exclude(
            live_session_id__in=participated
        ).select_related('live_session').order_by('-created_at')

        data = [
            {
                'id': n.id,
                'session_id': n.live_session.id,
                'session_title': n.live_session.title or n.live_session.lecture.title,
                'session_code': n.live_session.session_code,
                'session_date': n.live_session.started_at,
                'content': n.content,
                'stats': n.stats,
                'has_self_test': True,  # C1: 셀프 테스트 가능 표시
                'linked_materials': [
                    {'id': m.id, 'title': m.title, 'file_type': m.file_type, 'file_url': m.file.url if m.file else ''}
                    for m in n.linked_materials.all()
                ],
            }
            for n in absent_notes
        ]

        return Response({
            'absent_notes': data,
            'total': len(data),
        })


class AbsentSelfTestView(APIView):
    """
    POST /api/learning/absent-notes/{note_id}/self-test/
    C1: 결석생 셀프 테스트 — 노트 내용 기반 미니 퀴즈 3문항 AI 생성
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, note_id):
        import openai
        import os
        import json

        note = get_object_or_404(LiveSessionNote, id=note_id, is_public=True, is_approved=True, status='DONE')
        session = note.live_session

        # 참가자가 아닌 학생만 (결석생)
        if session.participants.filter(student=request.user).exists():
            return Response({'error': '출석한 세션입니다. 셀프 테스트 대상이 아닙니다.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            # [RAG] 공식 문서에서 관련 컨텍스트 검색
            rag_context = ""
            try:
                from .rag import RAGService
                rag = RAGService()
                lecture_id = session.lecture_id if session.lecture else None
                related_docs = rag.search(query=note.content[:500], top_k=2, lecture_id=lecture_id)
                if related_docs:
                    rag_context = "\n".join([f"- {doc.content[:200]}" for doc in related_docs])
                    print(f"✅ [RAG] 결석생 셀프 테스트에 공식 문서 {len(related_docs)}건 참조")
            except Exception as rag_err:
                print(f"⚠️ [RAG] 셀프 테스트 검색 실패: {rag_err}")

            user_content = f'강의 노트:\n{note.content[:4000]}'
            if rag_context:
                user_content += f'\n\n[공식 문서 참조 (정확성 보장용)]:\n{rag_context}'

            response = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': (
                        '아래 강의 노트를 읽은 결석생이 핵심 내용을 이해했는지 확인하는 '
                        '미니 퀴즈 3문항(4지선다)을 생성하세요.\n'
                        '[공식 문서 참조]가 있으면 정확한 정의에 기반한 문제를 출제하세요.\n'
                        '반드시 아래 JSON 배열 형식으로만 응답하세요:\n'
                        '[{"question":"문제","options":["A","B","C","D"],"correct_answer":"정답","explanation":"해설"}, ...]'
                    )},
                    {'role': 'user', 'content': user_content}
                ],
                temperature=0.5,
                max_tokens=1500,
            )
            raw = response.choices[0].message.content.strip()
            if '```' in raw:
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            questions = json.loads(raw)
            return Response({'questions': questions, 'note_id': note_id})

        except Exception as e:
            return Response({'error': f'셀프 테스트 생성 실패: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

