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
        # 결석생 공개 여부 (선택)
        make_public = request.data.get('is_public', False)
        note.is_public = make_public
        note.save()

        return Response({
            'ok': True,
            'is_approved': True,
            'is_public': note.is_public,
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
