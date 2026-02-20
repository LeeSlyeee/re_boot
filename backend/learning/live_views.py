"""
라이브 세션 API Views
Phase 0: 세션 생성/입장/종료 + 교안 업로드 + 이해도 펄스
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Count

from .models import (
    LiveSession, LiveParticipant, LectureMaterial, LiveSTTLog,
    Lecture, LearningSession, PulseCheck
)


# ══════════════════════════════════════════════════════════
# 교수자: 라이브 세션 관리
# ══════════════════════════════════════════════════════════

class LiveSessionViewSet(viewsets.ViewSet):
    """
    교수자 전용: 라이브 세션 CRUD
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='create')
    def create_session(self, request):
        """
        POST /api/learning/live/create/
        라이브 세션 생성 + 6자리 코드 발급
        """
        lecture_id = request.data.get('lecture_id')
        title = request.data.get('title', '')

        if not lecture_id:
            return Response({'error': 'lecture_id는 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)

        # 이미 진행 중인 세션이 있는지 확인
        active_session = LiveSession.objects.filter(
            lecture=lecture,
            status__in=['WAITING', 'LIVE']
        ).first()

        if active_session:
            return Response({
                'error': '이미 진행 중인 세션이 있습니다.',
                'session_id': active_session.id,
                'session_code': active_session.session_code,
            }, status=status.HTTP_409_CONFLICT)

        session = LiveSession.objects.create(
            lecture=lecture,
            instructor=request.user,
            title=title,
            status='WAITING',
        )

        return Response({
            'id': session.id,
            'session_code': session.session_code,
            'status': session.status,
            'title': session.title or lecture.title,
            'lecture_id': lecture.id,
            'lecture_title': lecture.title,
            'created_at': session.created_at,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='start')
    def start_session(self, request, pk=None):
        """
        POST /api/learning/live/{id}/start/
        세션을 WAITING → LIVE 상태로 변경
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)

        if session.status != 'WAITING':
            return Response({'error': f'현재 상태({session.status})에서는 시작할 수 없습니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        session.status = 'LIVE'
        session.started_at = timezone.now()
        session.save()

        return Response({
            'id': session.id,
            'status': session.status,
            'started_at': session.started_at,
            'participant_count': session.participants.filter(is_active=True).count(),
        })

    @action(detail=True, methods=['post'], url_path='end')
    def end_session(self, request, pk=None):
        """
        POST /api/learning/live/{id}/end/
        세션 종료
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)

        if session.status == 'ENDED':
            return Response({'error': '이미 종료된 세션입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        session.status = 'ENDED'
        session.ended_at = timezone.now()
        session.save()

        # 참가자 전원 비활성화
        session.participants.update(is_active=False)

        return Response({
            'id': session.id,
            'status': session.status,
            'ended_at': session.ended_at,
            'total_participants': session.participants.count(),
        })

    @action(detail=True, methods=['get'], url_path='status')
    def session_status(self, request, pk=None):
        """
        GET /api/learning/live/{id}/status/
        세션 상태 + 참가자 수 조회 (교수자용 폴링 엔드포인트)
        """
        session = get_object_or_404(LiveSession, id=pk)

        # 권한: 교수자이거나 해당 세션 참가자
        is_instructor = session.instructor == request.user
        is_participant = session.participants.filter(student=request.user).exists()

        if not is_instructor and not is_participant:
            return Response({'error': '접근 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)

        active_count = session.participants.filter(is_active=True).count()
        total_count = session.participants.count()

        data = {
            'id': session.id,
            'session_code': session.session_code,
            'status': session.status,
            'title': session.title or session.lecture.title,
            'lecture_id': session.lecture_id,
            'lecture_title': session.lecture.title,
            'started_at': session.started_at,
            'ended_at': session.ended_at,
            'active_participants': active_count,
            'total_participants': total_count,
            'is_instructor': is_instructor,
        }

        # 교수자에게만 참가자 목록 제공
        if is_instructor:
            participants = session.participants.select_related('student').all()
            data['participants'] = [
                {
                    'id': p.id,
                    'username': p.student.username,
                    'is_active': p.is_active,
                    'joined_at': p.joined_at,
                }
                for p in participants
            ]

        return Response(data)

    @action(detail=False, methods=['get'], url_path='active')
    def active_sessions(self, request):
        """
        GET /api/learning/live/active/
        교수자의 활성 세션 목록
        """
        sessions = LiveSession.objects.filter(
            instructor=request.user,
            status__in=['WAITING', 'LIVE']
        )

        data = [
            {
                'id': s.id,
                'session_code': s.session_code,
                'status': s.status,
                'title': s.title or s.lecture.title,
                'lecture_id': s.lecture_id,
                'participant_count': s.participants.filter(is_active=True).count(),
                'created_at': s.created_at,
            }
            for s in sessions
        ]

        return Response(data)

    # ── Step 2: 이해도 펄스 ──

    @action(detail=True, methods=['post'], url_path='pulse')
    def send_pulse(self, request, pk=None):
        """
        POST /api/learning/live/{id}/pulse/
        학생이 이해도 펄스 전송 (✅ UNDERSTAND / ❓ CONFUSED)
        동일 학생은 update_or_create로 최신 1건만 유지
        """
        session = get_object_or_404(LiveSession, id=pk, status='LIVE')

        # 참가자 확인
        if not session.participants.filter(student=request.user).exists():
            return Response({'error': '이 세션에 참가하지 않았습니다.'}, status=status.HTTP_403_FORBIDDEN)

        pulse_type = request.data.get('pulse_type', '').upper()
        if pulse_type not in ('UNDERSTAND', 'CONFUSED'):
            return Response({'error': 'pulse_type은 UNDERSTAND 또는 CONFUSED여야 합니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        pulse, created = PulseCheck.objects.update_or_create(
            live_session=session,
            student=request.user,
            defaults={'pulse_type': pulse_type}
        )

        return Response({
            'pulse_type': pulse.pulse_type,
            'updated': not created,
        })

    @action(detail=True, methods=['get'], url_path='pulse-stats')
    def pulse_stats(self, request, pk=None):
        """
        GET /api/learning/live/{id}/pulse-stats/
        교수자용: 실시간 이해도 비율 조회
        """
        session = get_object_or_404(LiveSession, id=pk)

        # 권한: 교수자이거나 참가자
        is_instructor = session.instructor == request.user
        if not is_instructor and not session.participants.filter(student=request.user).exists():
            return Response({'error': '접근 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)

        # 전체 펄스 통계
        stats = session.pulses.values('pulse_type').annotate(count=Count('id'))
        understand = 0
        confused = 0
        for s in stats:
            if s['pulse_type'] == 'UNDERSTAND':
                understand = s['count']
            elif s['pulse_type'] == 'CONFUSED':
                confused = s['count']

        total = understand + confused
        understand_rate = round((understand / total) * 100, 1) if total > 0 else 0

        return Response({
            'understand': understand,
            'confused': confused,
            'total': total,
            'understand_rate': understand_rate,
        })


# ══════════════════════════════════════════════════════════
# 학습자: 세션 입장
# ══════════════════════════════════════════════════════════

class JoinLiveSessionView(APIView):
    """
    POST /api/learning/live/join/
    학생이 6자리 코드로 라이브 세션 입장
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_code = request.data.get('session_code', '').strip().upper()

        if not session_code or len(session_code) != 6:
            return Response({'error': '6자리 세션 코드를 입력해주세요.'},
                            status=status.HTTP_400_BAD_REQUEST)

        session = LiveSession.objects.filter(
            session_code=session_code,
            status__in=['WAITING', 'LIVE']
        ).first()

        if not session:
            return Response({'error': '유효하지 않거나 종료된 세션 코드입니다.'},
                            status=status.HTTP_404_NOT_FOUND)

        # 이미 참가한 경우 → 재입장 처리
        existing = LiveParticipant.objects.filter(
            live_session=session,
            student=request.user
        ).first()

        if existing:
            existing.is_active = True
            existing.save()
            return Response({
                'message': '세션에 재입장했습니다.',
                'session_id': session.id,
                'session_code': session.session_code,
                'status': session.status,
                'title': session.title or session.lecture.title,
                'learning_session_id': existing.learning_session_id,
            })

        # 개인 LearningSession 자동 생성
        learning_session = LearningSession.objects.create(
            student=request.user,
            lecture=session.lecture,
            session_order=1,
        )

        # 참가자 등록
        participant = LiveParticipant.objects.create(
            live_session=session,
            student=request.user,
            learning_session=learning_session,
        )

        # 해당 강의에 수강 등록되어 있지 않으면 자동 등록
        if not session.lecture.students.filter(id=request.user.id).exists():
            session.lecture.students.add(request.user)

        return Response({
            'message': '세션에 입장했습니다.',
            'session_id': session.id,
            'session_code': session.session_code,
            'status': session.status,
            'title': session.title or session.lecture.title,
            'learning_session_id': learning_session.id,
        }, status=status.HTTP_201_CREATED)


# ══════════════════════════════════════════════════════════
# 교안 업로드
# ══════════════════════════════════════════════════════════

class LectureMaterialViewSet(viewsets.ViewSet):
    """
    교수자 전용: 교안 파일 업로드 및 조회
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @action(detail=False, methods=['post'], url_path='upload')
    def upload_material(self, request):
        """
        POST /api/learning/materials/upload/
        교안 파일 업로드
        """
        lecture_id = request.data.get('lecture_id')
        title = request.data.get('title', '')
        file = request.FILES.get('file')

        if not lecture_id or not file:
            return Response({'error': 'lecture_id와 file은 필수입니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)

        # 파일 타입 감지
        ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
        file_type_map = {
            'pdf': 'PDF',
            'ppt': 'PPT', 'pptx': 'PPT',
            'md': 'MD', 'markdown': 'MD',
        }
        file_type = file_type_map.get(ext, 'OTHER')

        material = LectureMaterial.objects.create(
            lecture=lecture,
            title=title or file.name,
            file=file,
            file_type=file_type,
            uploaded_by=request.user,
        )

        return Response({
            'id': material.id,
            'title': material.title,
            'file_type': material.file_type,
            'file_url': material.file.url if material.file else None,
            'uploaded_at': material.uploaded_at,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='list')
    def list_materials(self, request):
        """
        GET /api/learning/materials/list/?lecture_id=1
        교안 목록 조회
        """
        lecture_id = request.query_params.get('lecture_id')
        if not lecture_id:
            return Response({'error': 'lecture_id 쿼리 파라미터가 필요합니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        materials = LectureMaterial.objects.filter(lecture_id=lecture_id)

        data = [
            {
                'id': m.id,
                'title': m.title,
                'file_type': m.file_type,
                'file_url': m.file.url if m.file else None,
                'uploaded_at': m.uploaded_at,
            }
            for m in materials
        ]

        return Response(data)

    @action(detail=True, methods=['delete'], url_path='delete')
    def delete_material(self, request, pk=None):
        """
        DELETE /api/learning/materials/{id}/delete/
        교안 삭제
        """
        material = get_object_or_404(LectureMaterial, id=pk, uploaded_by=request.user)
        material.file.delete(save=False)  # 파일 삭제
        material.delete()
        return Response({'message': '교안이 삭제되었습니다.'}, status=status.HTTP_204_NO_CONTENT)
