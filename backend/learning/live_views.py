from .utils_text import check_answer_match
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
    Lecture, LearningSession, PulseCheck, PulseLog, LiveQuiz, LiveQuizResponse,
    LiveQuestion, LiveSessionNote, WeakZoneAlert, NoteViewLog,
    PlacementResult, SpacedRepetitionItem, StudentSkill, Skill
)

import openai
import os
import json
import base64
import logging
import threading
import numpy as np
from datetime import timedelta
openai.api_key = os.getenv('OPENAI_API_KEY')

logger = logging.getLogger(__name__)


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

        try:
            session.status = 'ENDED'
            session.ended_at = timezone.now()
            # WAITING 상태에서 바로 종료 시 started_at이 None → 현재 시간으로 설정
            if not session.started_at:
                session.started_at = session.ended_at
            session.save()

            # 참가자 전원 비활성화
            session.participants.update(is_active=False)

            # 활성 퀴즈 비활성화
            session.quizzes.filter(is_active=True).update(is_active=False)

            # OCI 환경: CMD 종료는 교수 PC의 WebSocket Agent가 담당
            # (프론트엔드에서 ws://localhost:5555 STOP 명령으로 처리)

            # 통합 노트 생성 시작 (비동기) — 중복 방지
            existing_note = LiveSessionNote.objects.filter(live_session=session).first()
            if not existing_note:
                note = LiveSessionNote.objects.create(live_session=session, status='PENDING')
                thread = threading.Thread(target=_generate_live_note, args=(session.id, note.id))
                thread.daemon = True
                thread.start()
                note_status = 'PENDING'
            else:
                note_status = existing_note.status

            return Response({
                'id': session.id,
                'status': session.status,
                'ended_at': session.ended_at,
                'total_participants': session.participants.count(),
                'note_status': note_status,
            })
        except Exception as e:
            print(f"❌ [EndSession] 세션 종료 처리 중 에러: {e}")
            return Response(
                {'error': f'세션 종료 처리 중 오류: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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

        # A2: 차시 자동 계산 (해당 강의의 종료된 세션 수 기반)
        ended_count = LiveSession.objects.filter(
            lecture=session.lecture, status='ENDED'
        ).count()
        week_number = ended_count + (1 if session.status != 'ENDED' else 0)

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
            'week_number': week_number,  # A2: 차시 번호
        }

        # 교수자에게만 참가자 목록 제공 (A1: 학생 레벨 포함)
        if is_instructor:
            participants = session.participants.select_related('student').all()
            # A1: 참가자별 최신 레벨 일괄 조회
            student_ids = [p.student_id for p in participants]
            level_map = {}
            for pr in PlacementResult.objects.filter(student_id__in=student_ids).order_by('student_id', '-created_at'):
                if pr.student_id not in level_map:
                    level_map[pr.student_id] = pr.level

            data['participants'] = [
                {
                    'id': p.id,
                    'username': p.student.username,
                    'is_active': p.is_active,
                    'joined_at': p.joined_at,
                    'level': level_map.get(p.student_id),  # A1: 1/2/3 or null
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

        # Phase 2: 이력 기록 (Weak Zone 감지용)
        PulseLog.objects.create(
            live_session=session,
            student=request.user,
            pulse_type=pulse_type,
        )

        # Phase 2-1: CONFUSED일 때 Weak Zone 감지
        weak_zone_alert = None
        if pulse_type == 'CONFUSED':
            from .weak_zone_utils import check_pulse_weak_zone
            weak_zone_alert = check_pulse_weak_zone(session, request.user)

        resp = {
            'pulse_type': pulse.pulse_type,
            'updated': not created,
        }
        if weak_zone_alert:
            resp['weak_zone_detected'] = True
        return Response(resp)

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

    # ── Step B: STT 수신 + 키워드 스팟팅 ──

    # 퀴즈 의도가 명확한 2어절 이상 키워드만 (STT 오인식 방지)
    # "퀴즈", "테스트" 등 단일 단어는 STT가 오인식하므로 제외
    TRIGGER_KEYWORDS = [
        '퀴즈 내', '퀴즈 시작', '퀴즈 풀', '퀴즈 한번', '퀴즈를 내', '퀴즈를 풀',
        '문제를 내', '문제 내볼', '문제를 풀', '문제 풀어',
        '확인 문제', '점검해 보', '체크해 보',
        '이해했는지', '이해도 확인',
    ]

    @action(detail=True, methods=['post'], url_path='stt')
    def receive_stt(self, request, pk=None):
        """
        POST /api/learning/live/{id}/stt/
        교수자 브라우저 Web Speech API → STT 청크 수신
        키워드 감지 시 자동으로 AI 퀴즈 제안 생성 (백그라운드)
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user, status='LIVE')

        text = request.data.get('text', '').strip()
        if not text:
            return Response({'error': 'text는 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # STT 로그 저장
        last_seq = session.stt_logs.order_by('-sequence_order').values_list('sequence_order', flat=True).first() or 0
        LiveSTTLog.objects.create(
            live_session=session,
            sequence_order=last_seq + 1,
            text_chunk=text,
        )

        # 키워드 스팟팅
        keyword_detected = None
        for kw in self.TRIGGER_KEYWORDS:
            if kw in text:
                keyword_detected = kw
                break

        quiz_suggestion_triggered = False
        if keyword_detected:
            # 최근 5분 내 제안이 없을 때만 (스팸 방지)
            recent_suggestion = session.quizzes.filter(
                is_suggestion=True, triggered_at__gte=timezone.now() - timedelta(minutes=5)
            ).exists()
            if not recent_suggestion:
                # 백그라운드에서 AI 퀴즈 제안 생성
                thread = threading.Thread(
                    target=_generate_quiz_suggestion, args=(session.id,)
                )
                thread.daemon = True
                thread.start()
                quiz_suggestion_triggered = True

        return Response({
            'sequence': last_seq + 1,
            'keyword_detected': keyword_detected,
            'quiz_suggestion_triggered': quiz_suggestion_triggered,
        })

    # ── Step B-2: 라즈베리 파이 KWS 웹훅 (Edge-Computing) ──

    @action(detail=False, methods=['post'], url_path='kws-webhook', permission_classes=[permissions.AllowAny])
    def kws_webhook(self, request):
        """
        POST /api/learning/live/kws-webhook/
        라즈베리 파이(Edge)에서 KWS 트리거 시 호출되는 웹훅 API.
        오디오 없이 텍스트 신호만 즉각 전달됨 (Zero Latency).
        
        페이로드 예시: {"keyword": "QUIZ", "confidence": 0.99}
        """
        keyword = request.data.get('keyword', '').upper()
        confidence = request.data.get('confidence', 1.0)
        
        # 1안 전략 (데모/단일 교수 환경): 현재 활성화(LIVE)된 가장 최근의 세션을 자동 타겟팅
        session = LiveSession.objects.filter(status='LIVE').order_by('-id').first()

        if not session:
            logger.warning(f"⚠️ [Edge KWS] 웹훅 수신됨 (키워드: {keyword}), 하지만 진행 중인 LIVE 세션이 없습니다.")
            return Response({'error': '현재 진행 중인 LIVE 세션이 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        logger.info(f"🎙️ [Edge KWS Webhook] 키워드 감지: session={session.id}, keyword={keyword}, confidence={confidence}")

        quiz_suggestion_triggered = False
        
        # 'QUIZ' 키워드로 퀴즈 제안 생성
        if keyword in ['QUIZ']:
            # 최근 5분 내 제안이 없을 때만 (스팸 방지)
            recent_suggestion = session.quizzes.filter(
                is_suggestion=True,
                triggered_at__gte=timezone.now() - timedelta(minutes=5)
            ).exists()
            
            if not recent_suggestion:
                thread = threading.Thread(
                    target=_generate_quiz_suggestion, args=(session.id,)
                )
                thread.daemon = True
                thread.start()
                quiz_suggestion_triggered = True
                logger.info(f"✅ [Edge KWS] 세션 {session.id}에 AI 퀴즈 제안이 성공적으로 트리거되었습니다.")

            return Response({
                'status': 'success',
                'keyword': keyword,
                'session_id': session.id,
                'quiz_suggestion_triggered': quiz_suggestion_triggered,
                'message': 'Quiz suggestion triggered.' if quiz_suggestion_triggered else 'Ignored (spam protection).'
            })
            
        return Response({'status': 'ignored', 'message': f'Unknown keyword: {keyword}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get', 'post'], url_path='rpi-status')
    def rpi_status(self, request):
        """
        [Phase 3] GET / POST /api/learning/live/rpi-status/
        프론트엔드(교수자 대시보드)에서 라즈베리 파이 IP 통신 상태를 체크하기 위한 API
        Django는 KWS 연산을 하지 않지만, 단순히 "그 IP와 포트가 열려있는지" 핑(Ping) 테스트만 대행합니다.
        """
        import socket
        
        # 세션 연동 없이 단순히 전역 상태처럼 관리 (프론트 UI용)
        # 실제 KWS는 Raspberry Pi -> Django 로의 단방향 웹훅이므로, 여기서 맺은 소켓 연결을 유지하지 않습니다.
        
        if request.method == 'POST':
            host = request.data.get('host', '').strip()
            port = request.data.get('port', 9999)
            manual_launch = request.data.get('manual_launch', False)
            
            if not host:
                return Response({'error': 'IP 주소가 필요합니다.'}, status=400)
                
            # TCP 소켓 연결 테스트 (Ping 기능)
            is_connected = False
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(2.0) # 2초 컷
                test_socket.connect((host, int(port)))
                is_connected = True
                test_socket.close() # 핑만 쳐보고 바로 닫음
            except Exception as e:
                is_connected = False
                
            # OCI 환경: 마이크 클라이언트 실행은 교수 PC의 WebSocket Agent가 담당
            # (프론트엔드에서 ws://localhost:5555 START 명령으로 처리)

            # 결과를 임시 메모리 장부에 기록 (단일 서버 가정)
            # (보다 완벽하게 하려면 Redis나 DB 등 활용 권장)
            request.session['rpi_host'] = host
            request.session['rpi_port'] = int(port)
            request.session['rpi_connected'] = is_connected
            
            return Response({
                'rpi_connected': is_connected,
                'rpi_host': host,
                'rpi_port': port
            })
            
        else: # GET
            host = request.session.get('rpi_host', '')
            port = request.session.get('rpi_port', 9999)
            is_connected = request.session.get('rpi_connected', False)
            
            # GET 요청 시마다 다시 한번 핑을 쳐서 살아있는지 확인 최신화
            if host:
                try:
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_socket.settimeout(1.0)
                    test_socket.connect((host, int(port)))
                    is_connected = True
                    test_socket.close()
                except:
                    is_connected = False
            
            return Response({
                'rpi_connected': is_connected,
                'rpi_host': host,
                'rpi_port': port
            })

    @action(detail=True, methods=['get'], url_path='stt-feed')
    def stt_feed(self, request, pk=None):
        """
        GET /api/learning/live/{id}/stt-feed/?after_seq=0
        학생용: 교수자 STT 실시간 자막 조회 (폴링)
        """
        session = get_object_or_404(LiveSession, id=pk)
        after_seq = int(request.query_params.get('after_seq', 0))
        logs = session.stt_logs.filter(sequence_order__gt=after_seq).order_by('sequence_order')[:20]
        return Response([
            {
                'id': log.id,
                'seq': log.sequence_order,
                'text': log.text_chunk,
                'timestamp': log.created_at.strftime('%H:%M:%S') if log.created_at else '',
            }
            for log in logs
        ])

    @action(detail=True, methods=['get'], url_path='quiz/suggestion')
    def quiz_suggestion(self, request, pk=None):
        """
        GET /api/learning/live/{id}/quiz/suggestion/
        교수자용: 미승인 AI 퀴즈 제안 조회 (폴링)
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        suggestion = session.quizzes.filter(is_suggestion=True, is_active=False).order_by('-triggered_at').first()

        if not suggestion:
            return Response(None)

        return Response({
            'id': suggestion.id,
            'question_text': suggestion.question_text,
            'options': suggestion.options,
            'correct_answer': suggestion.correct_answer,
            'explanation': suggestion.explanation,
            'triggered_at': suggestion.triggered_at,
        })

    @action(detail=True, methods=['post'], url_path=r'quiz/(?P<quiz_id>\d+)/approve')
    def approve_quiz(self, request, pk=None, quiz_id=None):
        """
        POST /api/learning/live/{id}/quiz/{qid}/approve/
        교수자가 AI 제안 퀴즈를 승인 → 전체 학생에게 발동
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user, status='LIVE')
        quiz = get_object_or_404(LiveQuiz, id=quiz_id, live_session=session, is_suggestion=True)

        # 기존 활성 퀴즈 비활성화
        session.quizzes.filter(is_active=True).update(is_active=False)

        # 제안 → 활성으로 전환
        quiz.is_suggestion = False
        quiz.is_active = True
        quiz.time_limit = int(request.data.get('time_limit', 60))
        quiz.triggered_at = timezone.now()  # 발동 시점 갱신
        quiz.save()

        return Response({
            'id': quiz.id,
            'question_text': quiz.question_text,
            'options': quiz.options,
            'is_active': True,
            'time_limit': quiz.time_limit,
            'triggered_at': quiz.triggered_at,
        })

    @action(detail=True, methods=['post'], url_path=r'quiz/(?P<quiz_id>\d+)/dismiss')
    def dismiss_quiz(self, request, pk=None, quiz_id=None):
        """
        POST /api/learning/live/{id}/quiz/{qid}/dismiss/
        교수자가 AI 제안 퀴즈를 무시 → DB에서 삭제
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        deleted, _ = LiveQuiz.objects.filter(
            id=quiz_id, live_session=session, is_suggestion=True
        ).delete()
        return Response({'dismissed': deleted > 0})

    # ── Step 3: 체크포인트 퀴즈 ──

    @action(detail=True, methods=['post'], url_path='quiz/create')
    def create_quiz(self, request, pk=None):
        """
        POST /api/learning/live/{id}/quiz/create/
        교수자가 퀴즈 직접 입력하여 발동
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user, status='LIVE')

        question_text = request.data.get('question_text', '')
        options = request.data.get('options', [])
        correct_answer = request.data.get('correct_answer', '')
        explanation = request.data.get('explanation', '')

        if not question_text or not options or not correct_answer:
            return Response({'error': 'question_text, options, correct_answer는 필수입니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # 기존 활성 퀴즈 비활성화
        session.quizzes.filter(is_active=True).update(is_active=False)

        quiz = LiveQuiz.objects.create(
            live_session=session,
            question_text=question_text,
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            is_ai_generated=False,
            time_limit=int(request.data.get('time_limit', 60)),
        )

        return Response({
            'id': quiz.id,
            'question_text': quiz.question_text,
            'options': quiz.options,
            'is_active': quiz.is_active,
            'time_limit': quiz.time_limit,
            'triggered_at': quiz.triggered_at,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='quiz/generate')
    def generate_quiz(self, request, pk=None):
        """
        POST /api/learning/live/{id}/quiz/generate/
        최근 STT 내용 기반 AI 퀴즈 자동 생성
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user, status='LIVE')

        # 최근 STT 로그 가져오기 (최근 10건)
        recent_stt = session.stt_logs.order_by('-sequence_order')[:10]
        stt_text = ' '.join([log.text_chunk for log in reversed(recent_stt)])

        if not stt_text.strip():
            return Response({'error': 'STT 데이터가 부족합니다. 조금 더 강의한 후 시도해주세요.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            # [RAG] 공식 문서에서 관련 컨텍스트 검색
            rag_context = ""
            try:
                from .rag import RAGService
                rag = RAGService()
                lecture_id = session.lecture_id if session.lecture else None
                related_docs = rag.search(query=stt_text[:300], top_k=2, lecture_id=lecture_id)
                if related_docs:
                    rag_context = "\n".join([f"- {doc.content[:200]}" for doc in related_docs])
                    print(f"✅ [RAG] 자동 퀴즈 생성에 공식 문서 {len(related_docs)}건 참조")
            except Exception as rag_err:
                print(f"⚠️ [RAG] 자동 퀴즈 검색 실패: {rag_err}")

            quiz_prompt = f'강의 내용:\n{stt_text[:2000]}'
            if rag_context:
                quiz_prompt += f'\n\n[공식 문서 참조 (정확성 보장용)]:\n{rag_context}'

            response = openai.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': (
                        '당신은 교육 전문가입니다. '
                        '주어진 강의 내용을 바탕으로 객관식 4지선다 퀴즈 1문제를 생성하세요. '
                        '[공식 문서 참조]가 있으면 정확한 정의에 기반한 문제를 출제하세요.\n'
                        '반드시 JSON 형식으로 응답하세요:\n'
                        '{"question": "문제", "options": ["A", "B", "C", "D"], "correct_answer": "정답", "explanation": "해설"}'
                    )},
                    {'role': 'user', 'content': quiz_prompt}
                ],
                temperature=0.7,
                max_tokens=500,
                response_format={'type': 'json_object'},
            )

            content = response.choices[0].message.content.strip()
            quiz_data = json.loads(content)

        except Exception as e:
            return Response({'error': f'AI 퀴즈 생성 실패: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 기존 활성 퀴즈 비활성화
        session.quizzes.filter(is_active=True).update(is_active=False)

        quiz = LiveQuiz.objects.create(
            live_session=session,
            question_text=quiz_data.get('question', ''),
            options=quiz_data.get('options', []),
            correct_answer=quiz_data.get('correct_answer', ''),
            explanation=quiz_data.get('explanation', ''),
            is_ai_generated=True,
        )

        return Response({
            'id': quiz.id,
            'question_text': quiz.question_text,
            'options': quiz.options,
            'correct_answer': quiz.correct_answer,
            'explanation': quiz.explanation,
            'is_ai_generated': True,
            'triggered_at': quiz.triggered_at,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='quiz/pending')
    def pending_quiz(self, request, pk=None):
        """
        GET /api/learning/live/{id}/quiz/pending/
        학생용: 미응답 활성 퀴즈 조회 (폴링 엔드포인트)
        """
        session = get_object_or_404(LiveSession, id=pk)
        if not session.participants.filter(student=request.user).exists():
            return Response({'error': '이 세션에 참가하지 않았습니다.'}, status=status.HTTP_403_FORBIDDEN)

        # 활성 퀴즈 중 내가 아직 응답하지 않은 것
        active_quizzes = session.quizzes.filter(is_active=True)
        pending = []
        for q in active_quizzes:
            if not q.responses.filter(student=request.user).exists():
                # 남은 시간 계산
                elapsed = (timezone.now() - q.triggered_at).total_seconds()
                remaining = max(0, q.time_limit - int(elapsed))
                if remaining > 0:  # 시간 지난 퀀즈는 제외
                    pending.append({
                        'id': q.id,
                        'question_text': q.question_text,
                        'options': q.options,
                        'time_limit': q.time_limit,
                        'remaining_seconds': remaining,
                        'triggered_at': q.triggered_at,
                    })

        return Response(pending)

    @action(detail=True, methods=['post'], url_path=r'quiz/(?P<quiz_id>\d+)/answer')
    def answer_quiz(self, request, pk=None, quiz_id=None):
        """
        POST /api/learning/live/{id}/quiz/{quiz_id}/answer/
        학생 퀴즈 응답 + 즉시 채점
        """
        session = get_object_or_404(LiveSession, id=pk)
        quiz = get_object_or_404(LiveQuiz, id=quiz_id, live_session=session)

        if not session.participants.filter(student=request.user).exists():
            return Response({'error': '이 세션에 참가하지 않았습니다.'}, status=status.HTTP_403_FORBIDDEN)

        # 중복 제출 방지
        if quiz.responses.filter(student=request.user).exists():
            return Response({'error': '이미 응답한 퀴즈입니다.'}, status=status.HTTP_409_CONFLICT)

        answer = request.data.get('answer', '')
        if not answer:
            return Response({'error': 'answer는 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        is_correct = check_answer_match(answer, quiz.correct_answer)

        response_obj = LiveQuizResponse.objects.create(
            quiz=quiz,
            student=request.user,
            answer=answer,
            is_correct=is_correct,
        )

        # Phase 2-1: Weak Zone 감지 트리거
        weak_zone_alert = None
        if not is_correct:
            from .weak_zone_utils import check_quiz_weak_zone
            weak_zone_alert = check_quiz_weak_zone(session, request.user, response_obj)

            # ── 학습 재설계 반영: SR 등록 + GapMap 업데이트 (비동기) ──
            def _update_learning_redesign():
                try:
                    from datetime import timedelta as _td
                    from django.utils import timezone as _tz
                    now = _tz.now()

                    concept = quiz.question_text[:60]  # 문제 자체를 개념명으로 사용
                    # 1) 간격반복(SR) 자동 등록
                    if not SpacedRepetitionItem.objects.filter(
                        student=request.user,
                        concept_name=concept[:200],
                    ).exists():
                        schedule = [
                            {'review_num': 1, 'label': '10분 후', 'due_at': (now + _td(minutes=10)).isoformat(), 'completed': False},
                            {'review_num': 2, 'label': '1일 후', 'due_at': (now + _td(days=1)).isoformat(), 'completed': False},
                            {'review_num': 3, 'label': '1주일 후', 'due_at': (now + _td(weeks=1)).isoformat(), 'completed': False},
                            {'review_num': 4, 'label': '1개월 후', 'due_at': (now + _td(days=30)).isoformat(), 'completed': False},
                        ]
                        SpacedRepetitionItem.objects.create(
                            student=request.user,
                            concept_name=concept[:200],
                            source_session=session,
                            review_question=quiz.question_text,
                            review_answer=quiz.correct_answer,
                            review_options=quiz.options or [],
                            schedule=schedule,
                        )
                        print(f"📝 [LiveQuiz→SR] {request.user.username}: '{concept}' SR 등록")

                    # 2) GapMap(StudentSkill) 업데이트 — 오답 개념 반영
                    try:
                        from .models import StudentSkill, Skill
                        # 문제 텍스트에서 매칭되는 스킬 탐색
                        skills = Skill.objects.all()
                        matched_skill = None
                        for s in skills:
                            if s.name.lower() in quiz.question_text.lower():
                                matched_skill = s
                                break
                        if matched_skill:
                            student_skill, _ = StudentSkill.objects.update_or_create(
                                student=request.user,
                                skill=matched_skill,
                                defaults={'status': 'WEAK'},
                            )
                            # progress 감소
                            if student_skill.progress > 0:
                                student_skill.progress = max(0, student_skill.progress - 10)
                                student_skill.save(update_fields=['progress'])
                            print(f"📊 [LiveQuiz→GapMap] {request.user.username}: {matched_skill.name} → WEAK")
                    except Exception as gm_err:
                        print(f"⚠️ [LiveQuiz→GapMap] 업데이트 실패: {gm_err}")

                except Exception as sr_err:
                    print(f"⚠️ [LiveQuiz→SR] 등록 실패: {sr_err}")

            thread = threading.Thread(target=_update_learning_redesign)
            thread.daemon = True
            thread.start()

        resp = {
            'is_correct': is_correct,
            'correct_answer': quiz.correct_answer,
            'explanation': quiz.explanation,
            'your_answer': answer,
        }
        if weak_zone_alert:
            resp['weak_zone_detected'] = True
        # A3: 오답 시 보충 설명 제공
        if not is_correct:
            resp['learning_redesign_triggered'] = True  # 프론트에 학습 재설계 트리거됨을 알림
            # WeakZone에서 AI 보충 설명 가져오기
            recent_wz = WeakZoneAlert.objects.filter(
                live_session=session, student=request.user,
            ).order_by('-created_at').first()
            if recent_wz and recent_wz.ai_suggested_content:
                resp['supplement_content'] = recent_wz.ai_suggested_content
            # 관련 교안 자료가 있으면 포함
            materials = session.lecture.materials.all()[:3]
            if materials:
                resp['related_materials'] = [
                    {'id': m.id, 'title': m.title, 'file_type': m.file_type}
                    for m in materials
                ]
        return Response(resp)

    @action(detail=True, methods=['get'], url_path=r'quiz/(?P<quiz_id>\d+)/results')
    def quiz_results(self, request, pk=None, quiz_id=None):
        """
        GET /api/learning/live/{id}/quiz/{quiz_id}/results/
        교수자용: 퀴즈 결과 통계
        """
        session = get_object_or_404(LiveSession, id=pk)
        quiz = get_object_or_404(LiveQuiz, id=quiz_id, live_session=session)

        if session.instructor != request.user:
            return Response({'error': '교수자만 조회 가능합니다.'}, status=status.HTTP_403_FORBIDDEN)

        responses = quiz.responses.select_related('student').all()
        total = responses.count()
        correct = responses.filter(is_correct=True).count()
        total_participants = session.participants.filter(is_active=True).count()

        # 보기별 선택 분포 계산
        option_distribution = {}
        for opt in (quiz.options or []):
            option_distribution[opt] = responses.filter(answer=opt).count()

        return Response({
            'quiz_id': quiz.id,
            'question_text': quiz.question_text,
            'options': quiz.options or [],
            'correct_answer': quiz.correct_answer,
            'is_ai_generated': quiz.is_ai_generated,
            'total_responses': total,
            'correct_count': correct,
            'accuracy': round((correct / total) * 100, 1) if total > 0 else 0,
            'total_participants': total_participants,
            'response_rate': round((total / total_participants) * 100, 1) if total_participants > 0 else 0,
            'option_distribution': option_distribution,
            'responses': [
                {
                    'username': r.student.username,
                    'answer': r.answer,
                    'is_correct': r.is_correct,
                    'responded_at': r.responded_at,
                }
                for r in responses
            ],
        })

    # ── Step 4: Q&A (기존 챗봇 자동 연동) ──

    @action(detail=True, methods=['get'], url_path='questions')
    def list_questions(self, request, pk=None):
        """
        GET /api/learning/live/{id}/questions/
        교수자용: 익명 질문 목록 (공감순 정렬)
        """
        session = get_object_or_404(LiveSession, id=pk)
        if session.instructor != request.user:
            return Response({'error': '교수자만 조회 가능합니다.'}, status=status.HTTP_403_FORBIDDEN)

        questions = session.questions.all()
        data = [
            {
                'id': q.id,
                'question_text': q.question_text,
                'ai_answer': q.ai_answer,
                'instructor_answer': q.instructor_answer,
                'upvotes': q.upvotes,
                'is_answered': q.is_answered,
                'created_at': q.created_at,
            }
            for q in questions
        ]
        return Response(data)

    @action(detail=True, methods=['post'], url_path=r'questions/(?P<question_id>\d+)/answer')
    def answer_question(self, request, pk=None, question_id=None):
        """
        POST /api/learning/live/{id}/questions/{qid}/answer/
        교수자가 질문에 답변
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        question = get_object_or_404(LiveQuestion, id=question_id, live_session=session)

        answer_text = request.data.get('answer', '')
        if not answer_text:
            return Response({'error': 'answer는 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        question.instructor_answer = answer_text
        question.is_answered = True
        question.save()

        return Response({'id': question.id, 'is_answered': True, 'instructor_answer': answer_text})

    @action(detail=True, methods=['post'], url_path=r'questions/(?P<question_id>\d+)/upvote')
    def upvote_question(self, request, pk=None, question_id=None):
        """
        POST /api/learning/live/{id}/questions/{qid}/upvote/
        학생이 다른 학생의 질문에 공감
        """
        session = get_object_or_404(LiveSession, id=pk)
        if not session.participants.filter(student=request.user).exists():
            return Response({'error': '참가자만 공감할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)

        question = get_object_or_404(LiveQuestion, id=question_id, live_session=session)
        question.upvotes += 1
        question.save()

        return Response({'id': question.id, 'upvotes': question.upvotes})

    @action(detail=True, methods=['get'], url_path='questions/feed')
    def question_feed(self, request, pk=None):
        """
        GET /api/learning/live/{id}/questions/feed/
        학생용: 전체 질문 목록 (공감순, 답변 상태 포함)
        """
        session = get_object_or_404(LiveSession, id=pk)
        if not session.participants.filter(student=request.user).exists():
            return Response({'error': '참가자만 조회 가능합니다.'}, status=status.HTTP_403_FORBIDDEN)

        all_questions = session.questions.all()  # ordering은 모델에서 -upvotes
        data = [
            {
                'id': q.id,
                'question_text': q.question_text,
                'ai_answer': q.ai_answer,
                'instructor_answer': q.instructor_answer,
                'upvotes': q.upvotes,
                'is_answered': q.is_answered,
                'created_at': q.created_at,
            }
            for q in all_questions
        ]
        return Response(data)

    @action(detail=True, methods=['post'], url_path='questions/ask')
    def ask_question(self, request, pk=None):
        """
        POST /api/learning/live/{id}/questions/ask/
        학생이 직접 Q&A 질문 등록 (익명)
        B1: 유사 질문 AI 자동 클러스터링 (비동기)
        """
        session = get_object_or_404(LiveSession, id=pk, status='LIVE')
        if not session.participants.filter(student=request.user).exists():
            return Response({'error': '참가자만 질문할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)

        text = request.data.get('question', '').strip()
        if not text:
            return Response({'error': 'question은 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        question = LiveQuestion.objects.create(
            live_session=session,
            student=request.user,
            question_text=text,
        )

        # B1: 비동기로 유사 질문 클러스터링
        thread = threading.Thread(
            target=_cluster_similar_question, args=(session.id, question.id)
        )
        thread.daemon = True
        thread.start()

        return Response({
            'id': question.id,
            'question_text': question.question_text,
            'upvotes': 0,
            'is_answered': False,
            'created_at': question.created_at,
        }, status=status.HTTP_201_CREATED)

    # ── Phase 2-1: Weak Zone Actions ──

    @action(detail=True, methods=['get'], url_path='weak-zones')
    def weak_zones(self, request, pk=None):
        """
        GET /api/learning/live/{id}/weak-zones/
        교수자용: 현재 세션의 Weak Zone 알림 목록
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        alerts = WeakZoneAlert.objects.filter(live_session=session).select_related('student', 'supplement_material')

        data = [
            {
                'id': a.id,
                'student_name': f"학생 #{a.student.id}",
                'trigger_type': a.trigger_type,
                'trigger_detail': a.trigger_detail,
                'status': a.status,
                'ai_suggested_content': a.ai_suggested_content,
                'supplement_material': {
                    'id': a.supplement_material.id,
                    'title': a.supplement_material.title,
                } if a.supplement_material else None,
                'created_at': a.created_at,
            }
            for a in alerts
        ]
        return Response({'weak_zones': data, 'total': len(data)})

    @action(detail=True, methods=['post'], url_path=r'weak-zones/(?P<wz_id>\d+)/push')
    def push_weak_zone(self, request, pk=None, wz_id=None):
        """
        POST /api/learning/live/{id}/weak-zones/{wz_id}/push/
        교수자: 보충 자료 푸시 승인 (material_id 선택 or AI 설명 사용)
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        alert = get_object_or_404(WeakZoneAlert, id=wz_id, live_session=session)

        material_id = request.data.get('material_id')
        if material_id:
            material = get_object_or_404(LectureMaterial, id=material_id, lecture=session.lecture)
            alert.supplement_material = material

        alert.status = 'MATERIAL_PUSHED'
        alert.save()

        return Response({'ok': True, 'status': alert.status})

    @action(detail=True, methods=['post'], url_path=r'weak-zones/(?P<wz_id>\d+)/dismiss')
    def dismiss_weak_zone(self, request, pk=None, wz_id=None):
        """
        POST /api/learning/live/{id}/weak-zones/{wz_id}/dismiss/
        교수자: Weak Zone 거부
        """
        session = get_object_or_404(LiveSession, id=pk, instructor=request.user)
        alert = get_object_or_404(WeakZoneAlert, id=wz_id, live_session=session)
        alert.status = 'DISMISSED'
        alert.save()
        return Response({'ok': True, 'status': 'DISMISSED'})

    @action(detail=True, methods=['get'], url_path='my-alerts')
    def my_alerts(self, request, pk=None):
        """
        GET /api/learning/live/{id}/my-alerts/
        학생용: 내 미해결 Weak Zone 알림 조회
        """
        session = get_object_or_404(LiveSession, id=pk)
        alerts = WeakZoneAlert.objects.filter(
            live_session=session,
            student=request.user,
            status__in=['DETECTED', 'MATERIAL_PUSHED'],
        )

        data = [
            {
                'id': a.id,
                'trigger_type': a.trigger_type,
                'status': a.status,
                'ai_suggested_content': a.ai_suggested_content,
                'supplement_material': {
                    'id': a.supplement_material.id,
                    'title': a.supplement_material.title,
                    'file_url': a.supplement_material.file.url if a.supplement_material.file else '',
                } if a.supplement_material else None,
                'created_at': a.created_at,
            }
            for a in alerts
        ]
        return Response({'alerts': data})

    @action(detail=True, methods=['post'], url_path=r'my-alerts/(?P<wz_id>\d+)/resolve')
    def resolve_alert(self, request, pk=None, wz_id=None):
        """
        POST /api/learning/live/{id}/my-alerts/{wz_id}/resolve/
        학생: 알림 확인 처리
        """
        session = get_object_or_404(LiveSession, id=pk)
        alert = get_object_or_404(WeakZoneAlert, id=wz_id, live_session=session, student=request.user)
        alert.status = 'RESOLVED'
        alert.save()
        return Response({'ok': True})

    @action(detail=True, methods=['get'], url_path='my-quiz-history')
    def my_quiz_history(self, request, pk=None):
        """
        GET /api/learning/live/{id}/my-quiz-history/
        학생용: 해당 세션에서 본인이 응답한 모든 퀴즈 결과 누적 조회
        """
        session = get_object_or_404(LiveSession, id=pk)

        # 해당 세션의 모든 퀴즈 (시간순)
        quizzes = LiveQuiz.objects.filter(
            live_session=session, is_suggestion=False
        ).order_by('triggered_at')

        results = []
        for quiz in quizzes:
            # 본인 응답 조회
            response = LiveQuizResponse.objects.filter(
                quiz=quiz, student=request.user
            ).first()

            results.append({
                'quiz_id': quiz.id,
                'question_text': quiz.question_text,
                'options': quiz.options or [],
                'correct_answer': quiz.correct_answer,
                'explanation': quiz.explanation or '',
                'is_ai_generated': quiz.is_ai_generated,
                'triggered_at': quiz.triggered_at,
                'my_answer': response.answer if response else None,
                'is_correct': response.is_correct if response else None,
                'responded_at': response.responded_at if response else None,
                'answered': response is not None,
            })

        total = len(results)
        answered = sum(1 for r in results if r['answered'])
        correct = sum(1 for r in results if r['is_correct'])

        return Response({
            'session_id': session.id,
            'session_title': session.title,
            'total_quizzes': total,
            'answered_count': answered,
            'correct_count': correct,
            'accuracy': round((correct / answered) * 100, 1) if answered > 0 else 0,
            'results': results,
        })

# ══════════════════════════════════════════════════════════
# 학습자: 강의 기반 퀴즈 누적 이력 (세션 상세 화면용)
# ══════════════════════════════════════════════════════════

class LectureQuizHistoryView(APIView):
    """
    GET /api/learning/lectures/<lecture_id>/quiz-history/
    학생용: 해당 강의의 모든 라이브 세션에서 본인이 응답한 퀴즈 결과 누적 조회
    (대시보드 > 수업목록 > 세션 상세 화면에서 사용)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id)

        # 해당 강의의 모든 라이브 세션 (최신순)
        live_sessions = LiveSession.objects.filter(
            lecture=lecture
        ).order_by('created_at')

        all_results = []
        total_quizzes = 0
        total_answered = 0
        total_correct = 0

        for session in live_sessions:
            quizzes = LiveQuiz.objects.filter(
                live_session=session, is_suggestion=False
            ).order_by('triggered_at')

            for quiz in quizzes:
                response = LiveQuizResponse.objects.filter(
                    quiz=quiz, student=request.user
                ).first()

                all_results.append({
                    'quiz_id': quiz.id,
                    'session_id': session.id,
                    'session_title': session.title or f'세션 #{session.id}',
                    'question_text': quiz.question_text,
                    'options': quiz.options or [],
                    'correct_answer': quiz.correct_answer,
                    'explanation': quiz.explanation or '',
                    'is_ai_generated': quiz.is_ai_generated,
                    'triggered_at': quiz.triggered_at,
                    'my_answer': response.answer if response else None,
                    'is_correct': response.is_correct if response else None,
                    'responded_at': response.responded_at if response else None,
                    'answered': response is not None,
                })
                total_quizzes += 1
                if response is not None:
                    total_answered += 1
                    if response.is_correct:
                        total_correct += 1

        return Response({
            'lecture_id': lecture.id,
            'lecture_title': lecture.title,
            'total_quizzes': total_quizzes,
            'answered_count': total_answered,
            'correct_count': total_correct,
            'accuracy': round((total_correct / total_answered) * 100, 1) if total_answered > 0 else 0,
            'results': all_results,
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
            logger.warning(f"⚠️ [JoinSession] 유효하지 않은 코드 시도: {session_code} (User: {request.user.username})")
            return Response({'error': '유효하지 않거나 종료된 세션 코드입니다.'},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            # 이미 참가한 경우 → 재입장 처리
            existing = LiveParticipant.objects.filter(
                live_session=session,
                student=request.user
            ).first()

            if existing:
                existing.is_active = True
                existing.save() # save() 호출 시 auto_now인 last_heartbeat가 자동 갱신됨
                return Response({
                    'message': '세션에 재입장했습니다.',
                    'session_id': session.id,
                    'session_code': session.session_code,
                    'status': session.status,
                    'title': session.title or session.lecture.title,
                    'lecture_id': session.lecture_id,
                    'learning_session_id': existing.learning_session_id if existing.learning_session_id else None,
                })

            # 개인 LearningSession 자동 생성 (중복 순번 방지)
            last_order = LearningSession.objects.filter(
                student=request.user,
                lecture=session.lecture
            ).order_by('-session_order').values_list('session_order', flat=True).first() or 0

            learning_session = LearningSession.objects.create(
                student=request.user,
                lecture=session.lecture,
                session_order=last_order + 1,
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
                'lecture_id': session.lecture_id,
                'learning_session_id': learning_session.id,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"❌ [JoinSession] 입장 처리 중 에러: {str(e)}")
            return Response({'error': f'입장 처리 중 서버 오류가 발생했습니다: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            'doc': 'DOCX', 'docx': 'DOCX',
            'md': 'MD', 'markdown': 'MD',
            'txt': 'TXT',
            'hwp': 'HWP', 'hwpx': 'HWP',
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


# ══════════════════════════════════════════════════════════
# 통합 노트 생성 (백그라운드)
# ══════════════════════════════════════════════════════════

def _generate_quiz_suggestion(session_id):
    """
    키워드 스팟팅 감지 후 백그라운드에서 실행.
    최근 STT 청크 기반으로 AI가 퀴즈 후보를 생성하고 is_suggestion=True로 저장.
    """
    import django
    django.setup()

    try:
        session = LiveSession.objects.get(id=session_id)
        recent_chunks = session.stt_logs.order_by('-sequence_order')[:10]
        if not recent_chunks:
            # DSCNN-only 모드: STT 없이 퀴즈 생성
            # 1순위: 교안 텍스트 기반
            materials = session.lecture.materials.all()[:2] if session.lecture else []
            material_text = ''
            for mat in materials:
                if mat.file and hasattr(mat.file, 'path'):
                    try:
                        with open(mat.file.path, 'r', encoding='utf-8', errors='ignore') as f:
                            material_text += f.read()[:2000]
                    except:
                        pass
            if material_text:
                context_text = material_text
                logger.info(f"📝 [DSCNN-only] STT 없음 → 교안 기반 퀴즈 생성 (세션 #{session_id})")
            else:
                # 2순위: 교안도 없으면 강의 제목/주제 기반 기본 퀴즈 생성
                lecture_title = session.lecture.title if session.lecture else '일반 수업'
                context_text = f"현재 '{lecture_title}' 강의가 진행 중입니다. 이 강의의 핵심 개념에 대한 이해도 확인 퀴즈를 생성해주세요."
                logger.info(f"📝 [DSCNN-only] STT·교안 모두 없음 → 강의 제목 기반 퀴즈 생성 (세션 #{session_id}, 강의: {lecture_title})")
        else:
            context_text = '\n'.join([c.text_chunk for c in reversed(recent_chunks)])



        # [RAG] 공식 문서에서 관련 컨텍스트 검색
        rag_context = ""
        try:
            from .rag import RAGService
            rag = RAGService()
            lecture_id = session.lecture_id if session.lecture else None
            related_docs = rag.search(query=context_text[:300], top_k=2, lecture_id=lecture_id)
            if related_docs:
                rag_context = "\n".join([f"- {doc.content[:200]}" for doc in related_docs])
                print(f"✅ [RAG] 라이브 퀴즈 제안에 공식 문서 {len(related_docs)}건 참조")
        except Exception as rag_err:
            print(f"⚠️ [RAG] 퀴즈 제안 검색 실패: {rag_err}")

        quiz_prompt = f'방금 교수자가 설명한 내용:\n{context_text}'
        if rag_context:
            quiz_prompt += f'\n\n[공식 문서 참조 (정확성 보장용)]:\n{rag_context}'

        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': (
                    '당신은 부트캠프 강의에서 교수자가 방금 설명한 내용을 바탕으로 '
                    '체크포인트 퀴즈를 생성하는 AI입니다.\n'
                    '[공식 문서 참조]가 있으면 정확한 정의에 기반한 문제를 출제하세요.\n'
                    '반드시 아래 JSON 형식으로 응답하세요:\n'
                    '{"question": "문제", "options": ["A", "B", "C", "D"], '
                    '"correct_answer": "정답", "explanation": "해설"}'
                )},
                {'role': 'user', 'content': quiz_prompt}
            ],
            temperature=0.7,
            max_tokens=500,
            response_format={'type': 'json_object'},
        )

        import json as json_module
        raw = response.choices[0].message.content.strip()
        quiz_data = json_module.loads(raw)

        LiveQuiz.objects.create(
            live_session=session,
            question_text=quiz_data['question'],
            options=quiz_data['options'],
            correct_answer=quiz_data['correct_answer'],
            explanation=quiz_data.get('explanation', ''),
            is_ai_generated=True,
            is_suggestion=True,   # 교수자 승인 대기
            is_active=False,      # 아직 학생에게 미발동
        )
        print(f"✅ [QuizSuggestion] 세션 #{session_id} AI 퀴즈 제안 생성 완료")

    except Exception as e:
        print(f"⚠️ [QuizSuggestion] 생성 실패: {e}")


def _generate_live_note(session_id, note_id):
    """
    세션 종료 후 백그라운드에서 실행.
    STT + 퀴즈 + Q&A + 이해도 데이터를 수집하여 GPT-4o로 통합 노트 생성.
    """
    import django
    django.setup()

    try:
        session = LiveSession.objects.get(id=session_id)
        note = LiveSessionNote.objects.get(id=note_id)

        # ── 1. STT 전문 수집 ──
        stt_logs = session.stt_logs.order_by('sequence_order')
        stt_text = '\n'.join([log.text_chunk for log in stt_logs])

        # ── 2. 퀴즈 결과 수집 ──
        quizzes = session.quizzes.all()
        quiz_summary = []
        for q in quizzes:
            total = q.responses.count()
            correct = q.responses.filter(is_correct=True).count()
            quiz_summary.append({
                'question': q.question_text,
                'options': q.options,
                'correct_answer': q.correct_answer,
                'total_responses': total,
                'correct_count': correct,
                'accuracy': round((correct / total) * 100, 1) if total > 0 else 0,
            })

        # ── 3. Q&A 수집 ──
        questions = session.questions.all()
        qa_summary = [
            {'question': q.question_text, 'ai_answer': q.ai_answer, 'instructor_answer': q.instructor_answer, 'upvotes': q.upvotes}
            for q in questions
        ]

        # ── 4. 이해도 통계 ──
        pulse_understand = session.pulses.filter(pulse_type='UNDERSTAND').count()
        pulse_confused = session.pulses.filter(pulse_type='CONFUSED').count()
        pulse_total = pulse_understand + pulse_confused
        understand_rate = round((pulse_understand / pulse_total) * 100, 1) if pulse_total > 0 else 0

        # ── 4-1. C2: 교안 콘텐츠 수집 (링크된 교안의 텍스트 추출) ──
        material_text = ''
        try:
            linked_mats = note.linked_materials.all() if hasattr(note, 'linked_materials') else []
            if not linked_mats:
                linked_mats = session.lecture.materials.all()[:3]
            for mat in linked_mats:
                if mat.file and hasattr(mat.file, 'path'):
                    try:
                        # 텍스트 파일이면 직접 읽기
                        with open(mat.file.path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()[:2000]
                            material_text += f"\n[교안: {mat.title}]\n{content}\n"
                    except:
                        material_text += f"\n[교안: {mat.title}] (파일 읽기 불가)\n"
        except:
            pass

        # ── 4-2. [RAG] 공식 문서에서 관련 컨텍스트 검색 ──
        rag_context = ''
        try:
            from .rag import RAGService
            rag = RAGService()
            search_query = stt_text[:500]
            related_docs = rag.search(query=search_query, top_k=3, lecture_id=session.lecture_id if session.lecture else None)
            if related_docs:
                rag_context = "\n".join([f"- {doc.content[:300]}" for doc in related_docs])
                print(f"✅ [RAG] 라이브 노트 생성에 공식 문서 {len(related_docs)}건 참조")
        except Exception as rag_err:
            print(f"⚠️ [RAG] 검색 실패 (노트는 STT만으로 진행): {rag_err}")

        # ── 5. 통계 저장 ──
        stats = {
            'total_participants': session.participants.count(),
            'stt_chunks': stt_logs.count(),
            'quiz_count': len(quiz_summary),
            'question_count': len(qa_summary),
            'understand_rate': understand_rate,
            'duration_minutes': 0,
            'material_count': len(material_text) > 0,  # C2: 교안 포함 여부
        }
        if session.started_at and session.ended_at:
            stats['duration_minutes'] = int((session.ended_at - session.started_at).total_seconds() / 60)

        note.stats = stats
        note.save()

        # ── 6. AI 통합 노트 생성 ──
        quiz_text = ''
        for i, q in enumerate(quiz_summary, 1):
            quiz_text += f"\n퀴즈 {i}: {q['question']}\n정답: {q['correct_answer']} | 정답률: {q['accuracy']}%\n"

        qa_text = ''
        for i, q in enumerate(qa_summary, 1):
            qa_text += f"\n질문 {i} (공감 {q['upvotes']}): {q['question']}\n"
            if q['instructor_answer']:
                qa_text += f"교수자 답변: {q['instructor_answer']}\n"
            elif q['ai_answer']:
                qa_text += f"AI 답변: {q['ai_answer'][:200]}\n"

        prompt_content = f"""[강의 시간: 약 {stats['duration_minutes']}분 | 참가자: {stats['total_participants']}명 | 이해도: {understand_rate}%]

=== 교안 원문 (텍스트 추출) ===
{material_text[:3000] if material_text else '(교안 없음)'}

=== 공식 문서 참조 (RAG 검색 결과) ===
{rag_context[:2000] if rag_context else '(참조 문서 없음)'}

=== 교수자 발화 STT 전문 ===
{stt_text[:8000]}

=== 체크포인트 퀴즈 결과 ({len(quiz_summary)}건) ===
{quiz_text if quiz_text else '(퀴즈 없음)'}

=== 학생 질문 ({len(qa_summary)}건) ===
{qa_text if qa_text else '(질문 없음)'}
"""

        try:
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            response = client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': (
                        '당신은 대학 강의를 전문적으로 정리하는 AI 어시스턴트입니다.\n'
                        '아래 강의 데이터(교안 원문, 공식 문서 참조, STT 전문, 퀴즈 결과, 학생 질문)를 기반으로\n'
                        '학생들이 복습하기 좋은 통합 노트를 작성하세요.\n\n'
                        '핵심 규칙:\n'
                        '- 교안에 있는 내용은 평문으로 정리하세요.\n'
                        '- 교수자가 STT에서 교안에 없는 추가 설명/예시/노하우를 말한 부분은\n'
                        '  "🎙️ 교수자 설명" 라벨을 붙여 구분하세요.\n'
                        '- [공식 문서 참조]가 있으면, 전문 용어의 정확한 정의와 코드 예시를\n'
                        '  "📖 공식 문서" 라벨로 보충하세요.\n'
                        '- 교안과 STT를 주제별로 통합 정리하세요 (별도 섹션으로 분리하지 마세요).\n\n'
                        '형식:\n'
                        '# 📚 강의 통합 노트\n\n'
                        '## 📋 수업 개요\n- 시간, 참가자, 이해도 등\n\n'
                        '## 📖 핵심 내용 정리\n### 1. 주제별 정리 (교안+🎙️ 통합)\n\n'
                        '## ✅ 체크포인트 퀴즈 복습\n- 문제, 정답, 해설\n\n'
                        '## ❓ 주요 질의응답\n- 학생 질문과 답변 정리\n\n'
                        '## 🔑 핵심 키워드\n- 중요 용어\n\n'
                        '## 📝 복습 포인트\n- 추가 학습 추천 사항'
                    )},
                    {'role': 'user', 'content': prompt_content}
                ],
                temperature=0.3,
                max_tokens=4000,
            )
            note.content = response.choices[0].message.content
            note.status = 'DONE'

        except Exception as e:
            # Fallback: 원문 기반 간이 노트
            note.content = (
                f"# 📚 강의 통합 노트 (자동 생성 대기중)\n\n"
                f"## 📋 수업 개요\n"
                f"- 시간: 약 {stats['duration_minutes']}분\n"
                f"- 참가자: {stats['total_participants']}명\n"
                f"- 이해도: {understand_rate}%\n\n"
                f"## 📖 강의 내용 (원문)\n{stt_text[:3000]}\n\n"
                f"## ✅ 퀴즈 ({len(quiz_summary)}건)\n{quiz_text}\n\n"
                f"## ❓ 질의응답 ({len(qa_summary)}건)\n{qa_text}\n"
            )
            note.status = 'DONE'  # Fallback이라도 DONE 처리
            print(f"⚠️ [LiveNote] GPT 실패, Fallback 사용: {e}")

        note.save()

        # ── 7. 교수자 인사이트 리포트 생성 ──
        try:
            insight_prompt = f"""[세션 통계]
- 참가자: {stats['total_participants']}명, 시간: {stats['duration_minutes']}분
- 이해도: {understand_rate}%, 퀴즈 {len(quiz_summary)}건, 질문 {len(qa_summary)}건

[퀴즈 결과]
{quiz_text if quiz_text else '(퀴즈 없음)'}

[학생 질문 (공감순)]
{qa_text if qa_text else '(질문 없음)'}

[이해도 데이터]
이해 {pulse_understand}명 / 혼란 {pulse_confused}명 = {understand_rate}%
"""
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            insight_resp = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': (
                        '당신은 부트캠프 교수자를 위한 수업 분석 AI입니다.\n'
                        '아래 세션 데이터를 분석하여 교수자 인사이트 리포트를 작성하세요.\n\n'
                        '형식:\n'
                        '# 📊 인사이트 리포트\n\n'
                        '## 🔴 주의 구간\n- 이해도가 낮았던 포인트, 혼란이 많았던 시점\n\n'
                        '## ❓ TOP 3 질문\n- 가장 많은 공감을 받은 질문과 의미\n\n'
                        '## 📝 퀴즈 분석\n- 정답률 낮은 문항 분석, 취약 개념\n\n'
                        '## 💡 다음 수업 제안\n- 보충 필요 주제, 수업 속도 조절 제안\n\n'
                        '## 📈 전체 평가\n- 긍정 포인트 + 개선 포인트 요약'
                    )},
                    {'role': 'user', 'content': insight_prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            note.instructor_insight = insight_resp.choices[0].message.content
            note.save()
            print(f"✅ [Insight] 교수자 인사이트 리포트 생성 완료")
        except Exception as ie:
            print(f"⚠️ [Insight] 인사이트 생성 실패 (노트는 정상): {ie}")

        # ── 8. Phase 2-3: 복습 루트 + 간격 반복 자동 생성 ──
        try:
            from .models import ReviewRoute, SpacedRepetitionItem
            from datetime import timedelta

            participants = LiveParticipant.objects.filter(live_session=session)

            for participant in participants:
                student = participant.student

                # 해당 학생의 오답 퀴즈 수집
                wrong_responses = LiveQuizResponse.objects.filter(
                    quiz__live_session=session,
                    student=student,
                    is_correct=False,
                ).select_related('quiz')

                # 복습 항목 구성
                items = []
                order = 1

                # 1순위: 통합 노트
                items.append({
                    'order': order, 'type': 'note',
                    'title': '오늘 수업 통합 노트',
                    'note_id': note.id, 'est_minutes': 10,
                })
                order += 1

                # 2순위: 오답 개념
                wrong_concepts = []
                for wr in wrong_responses:
                    concept = wr.quiz.question_text[:60]
                    items.append({
                        'order': order, 'type': 'concept',
                        'title': f'오답 복습: {concept}',
                        'content': f"문제: {wr.quiz.question_text}\n정답: {wr.quiz.correct_answer}\n{wr.quiz.explanation or ''}",
                        'est_minutes': 5,
                    })
                    wrong_concepts.append({
                        'concept': concept,
                        'quiz': wr.quiz,
                        'response': wr,
                    })
                    order += 1

                total_minutes = sum(i.get('est_minutes', 0) for i in items)

                # ReviewRoute 생성
                ReviewRoute.objects.update_or_create(
                    live_session=session,
                    student=student,
                    defaults={
                        'items': items,
                        'total_est_minutes': total_minutes,
                        'status': 'AUTO_APPROVED',
                    }
                )

                # SpacedRepetitionItem: 오답 개념마다 생성 (5주기)
                now = timezone.now()
                for wc in wrong_concepts:
                    # 중복 방지
                    if SpacedRepetitionItem.objects.filter(
                        student=student,
                        concept_name=wc['concept'][:200],
                        source_session=session,
                    ).exists():
                        continue

                    schedule = [
                        {'review_num': 1, 'label': '10분 후', 'due_at': (now + timedelta(minutes=10)).isoformat(), 'completed': False},
                        {'review_num': 2, 'label': '1일 후', 'due_at': (now + timedelta(days=1)).isoformat(), 'completed': False},
                        {'review_num': 3, 'label': '1주일 후', 'due_at': (now + timedelta(weeks=1)).isoformat(), 'completed': False},
                        {'review_num': 4, 'label': '1개월 후', 'due_at': (now + timedelta(days=30)).isoformat(), 'completed': False},
                        {'review_num': 5, 'label': '6개월 후', 'due_at': (now + timedelta(days=180)).isoformat(), 'completed': False},
                    ]

                    # AI로 복습 문항 생성
                    review_q = wc['quiz'].question_text
                    review_a = wc['quiz'].correct_answer
                    review_opts = wc['quiz'].options if hasattr(wc['quiz'], 'options') and wc['quiz'].options else []

                    SpacedRepetitionItem.objects.create(
                        student=student,
                        concept_name=wc['concept'][:200],
                        source_session=session,
                        source_quiz=wc['quiz'],
                        review_question=review_q,
                        review_answer=review_a,
                        review_options=review_opts,
                        schedule=schedule,
                    )

            print(f"✅ [ReviewRoute] 세션 #{session_id} - {participants.count()}명 복습 루트 생성 완료")
        except Exception as rre:
            print(f"⚠️ [ReviewRoute] 복습 루트 생성 실패 (노트는 정상): {rre}")

        print(f"✅ [LiveNote] 세션 #{session_id} 통합 노트 생성 완료 ({note.status})")

    except Exception as e:
        print(f"❌ [LiveNote] 노트 생성 실패: {e}")
        try:
            note = LiveSessionNote.objects.get(id=note_id)
            note.status = 'FAILED'
            note.content = f"노트 생성 실패: {str(e)}"
            note.save()
        except:
            pass


# ══════════════════════════════════════════════════════════
# B1: 유사 질문 AI 클러스터링 (백그라운드)
# ══════════════════════════════════════════════════════════

def _cluster_similar_question(session_id, question_id):
    """
    신규 질문과 기존 질문들을 비교하여 유사하면 같은 cluster_id를 부여.
    """
    import django
    django.setup()
    try:
        session = LiveSession.objects.get(id=session_id)
        new_q = LiveQuestion.objects.get(id=question_id)
        existing = session.questions.exclude(id=question_id).values_list('id', 'question_text', 'cluster_id')

        if not existing:
            # 첫 번째 질문 → cluster_id = question_id 자체
            new_q.cluster_id = new_q.id
            new_q.save()
            return

        # 기존 질문 목록 구성
        existing_list = [{'id': e[0], 'text': e[1], 'cluster': e[2]} for e in existing]
        existing_texts = '\n'.join([f"{i+1}. {e['text']}" for i, e in enumerate(existing_list)])

        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': (
                    '당신은 질문 유사도 판별 전문가입니다.\n'
                    '새 질문이 기존 질문 중 하나와 같은 의미인지 판단하세요.\n'
                    '같은 의미의 질문이 있으면 그 질문의 번호(1부터 시작)를 반환하세요.\n'
                    '없으면 0을 반환하세요.\n'
                    '숫자만 반환하세요. 설명 불필요.'
                )},
                {'role': 'user', 'content': f'기존 질문:\n{existing_texts}\n\n새 질문: {new_q.question_text}'}
            ],
            temperature=0,
            max_tokens=10,
        )
        result = response.choices[0].message.content.strip()
        match_idx = int(result) if result.isdigit() else 0

        if 1 <= match_idx <= len(existing_list):
            matched = existing_list[match_idx - 1]
            # 매칭된 질문의 cluster_id 사용 (없으면 해당 질문 id)
            new_q.cluster_id = matched['cluster'] or matched['id']
        else:
            new_q.cluster_id = new_q.id  # 새 클러스터
        new_q.save()
        print(f"✅ [Cluster] 질문 #{question_id} → cluster {new_q.cluster_id}")

    except Exception as e:
        print(f"⚠️ [Cluster] 클러스터링 실패: {e}")


# ══════════════════════════════════════════════════════════
# B2: 학습자 개인 요약 API
# ══════════════════════════════════════════════════════════

class StudentSessionSummaryView(APIView):
    """
    GET /api/learning/live/{session_id}/my-summary/
    학생용: 세션 종료 후 개인 맞춤 요약 (퀴즈 결과 + 펄스 + 어려웠던 개념)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id, status='ENDED')
        if not session.participants.filter(student=request.user).exists():
            return Response({'error': '이 세션에 참가하지 않았습니다.'}, status=status.HTTP_403_FORBIDDEN)

        # 퀴즈 결과
        my_responses = LiveQuizResponse.objects.filter(
            quiz__live_session=session, student=request.user
        ).select_related('quiz')
        total_quiz = my_responses.count()
        correct_quiz = my_responses.filter(is_correct=True).count()
        wrong_concepts = [
            r.quiz.question_text[:60] for r in my_responses if not r.is_correct
        ]

        # 펄스 기록
        my_pulses = PulseLog.objects.filter(
            live_session=session, student=request.user
        )
        pulse_total = my_pulses.count()
        pulse_confused = my_pulses.filter(pulse_type='CONFUSED').count()

        # WeakZone
        my_weak_zones = WeakZoneAlert.objects.filter(
            live_session=session, student=request.user
        ).values_list('trigger_detail', 'ai_suggested_content')

        weak_topics = []
        supplements = []
        for detail, ai_content in my_weak_zones:
            if isinstance(detail, dict) and detail.get('recent_topic'):
                weak_topics.append(detail['recent_topic'])
            if ai_content:
                supplements.append(ai_content[:200])

        return Response({
            'session_title': session.title or session.lecture.title,
            'quiz_total': total_quiz,
            'quiz_correct': correct_quiz,
            'quiz_accuracy': round((correct_quiz / total_quiz) * 100, 1) if total_quiz > 0 else None,
            'wrong_concepts': wrong_concepts,
            'pulse_total': pulse_total,
            'pulse_confused_count': pulse_confused,
            'pulse_confused_rate': round((pulse_confused / pulse_total) * 100, 1) if pulse_total > 0 else 0,
            'weak_topics': weak_topics,
            'supplement_tips': supplements,
            'message': _build_summary_message(total_quiz, correct_quiz, pulse_confused, pulse_total, weak_topics),
        })


def _build_summary_message(total_q, correct_q, confused, pulse_total, weak_topics):
    """개인 요약 메시지 생성 (AI 호출 없이 규칙 기반)"""
    parts = []
    if total_q > 0:
        acc = round((correct_q / total_q) * 100)
        if acc >= 80:
            parts.append(f"오늘 퀴즈 정답률 {acc}%로 훌륭합니다! 👏")
        elif acc >= 50:
            parts.append(f"퀴즈 정답률 {acc}%입니다. 오답 개념을 한번 더 복습해보세요.")
        else:
            parts.append(f"퀴즈 정답률이 {acc}%로 낮습니다. 아래 보충 자료로 개념을 다잡아보세요.")

    if pulse_total > 0 and confused > 0:
        rate = round((confused / pulse_total) * 100)
        if rate >= 50:
            parts.append(f"수업 중 혼란을 느낀 비율이 {rate}%입니다. 노트를 꼼꼼히 복습하세요. 📖")

    if weak_topics:
        parts.append(f"특히 '{', '.join(weak_topics[:3])}' 부분에 집중하면 좋겠습니다.")

    if not parts:
        parts.append("오늘 수업 수고하셨습니다! 통합 노트로 복습해보세요.")

    return ' '.join(parts)


# ══════════════════════════════════════════════════════════
# 통합 노트 관련 Views — note_views.py로 이동됨
# Re-export for backward compatibility (urls.py imports from .live_views)
# ══════════════════════════════════════════════════════════
from .note_views import LiveNoteView, NoteApproveView, NoteMaterialLinkView, AbsentNoteListView  # noqa: F401


