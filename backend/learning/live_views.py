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
    Lecture, LearningSession, PulseCheck, LiveQuiz, LiveQuizResponse,
    LiveQuestion, LiveSessionNote
)

import openai
import os
import json
import threading
openai.api_key = os.getenv('OPENAI_API_KEY')


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

        # 활성 퀴즈 비활성화
        session.quizzes.filter(is_active=True).update(is_active=False)

        # 통합 노트 생성 시작 (비동기)
        note = LiveSessionNote.objects.create(live_session=session, status='PENDING')
        thread = threading.Thread(target=_generate_live_note, args=(session.id, note.id))
        thread.daemon = True
        thread.start()

        return Response({
            'id': session.id,
            'status': session.status,
            'ended_at': session.ended_at,
            'total_participants': session.participants.count(),
            'note_status': 'PENDING',
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
        )

        return Response({
            'id': quiz.id,
            'question_text': quiz.question_text,
            'options': quiz.options,
            'is_active': quiz.is_active,
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
            response = openai.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': (
                        '당신은 교육 전문가입니다. '
                        '주어진 강의 내용을 바탕으로 객관식 4지선다 퀴즈 1문제를 생성하세요. '
                        '반드시 JSON 형식으로 응답하세요:\n'
                        '{"question": "문제", "options": ["A", "B", "C", "D"], "correct_answer": "정답", "explanation": "해설"}'
                    )},
                    {'role': 'user', 'content': f'강의 내용:\n{stt_text[:2000]}'}
                ],
                temperature=0.7,
                max_tokens=500,
            )

            content = response.choices[0].message.content.strip()
            # JSON 파싱 (코드 블록 제거)
            if '```' in content:
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
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
                pending.append({
                    'id': q.id,
                    'question_text': q.question_text,
                    'options': q.options,
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

        is_correct = answer.strip() == quiz.correct_answer.strip()

        response_obj = LiveQuizResponse.objects.create(
            quiz=quiz,
            student=request.user,
            answer=answer,
            is_correct=is_correct,
        )

        return Response({
            'is_correct': is_correct,
            'correct_answer': quiz.correct_answer,
            'explanation': quiz.explanation,
            'your_answer': answer,
        })

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

        return Response({
            'quiz_id': quiz.id,
            'question_text': quiz.question_text,
            'correct_answer': quiz.correct_answer,
            'total_responses': total,
            'correct_count': correct,
            'accuracy': round((correct / total) * 100, 1) if total > 0 else 0,
            'total_participants': total_participants,
            'response_rate': round((total / total_participants) * 100, 1) if total_participants > 0 else 0,
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
        학생용: 교수자 답변이 달린 질문 피드 (폴링)
        """
        session = get_object_or_404(LiveSession, id=pk)
        if not session.participants.filter(student=request.user).exists():
            return Response({'error': '참가자만 조회 가능합니다.'}, status=status.HTTP_403_FORBIDDEN)

        answered = session.questions.filter(is_answered=True)
        data = [
            {
                'id': q.id,
                'question_text': q.question_text,
                'instructor_answer': q.instructor_answer,
                'upvotes': q.upvotes,
                'created_at': q.created_at,
            }
            for q in answered
        ]
        return Response(data)

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


# ══════════════════════════════════════════════════════════
# 통합 노트 생성 (백그라운드)
# ══════════════════════════════════════════════════════════

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

        # ── 5. 통계 저장 ──
        stats = {
            'total_participants': session.participants.count(),
            'stt_chunks': stt_logs.count(),
            'quiz_count': len(quiz_summary),
            'question_count': len(qa_summary),
            'understand_rate': understand_rate,
            'duration_minutes': 0,
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

=== 강의 STT 전문 ===
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
                        '아래 강의 데이터(STT 전문, 퀴즈 결과, 학생 질문)를 기반으로\n'
                        '학생들이 복습하기 좋은 통합 노트를 작성하세요.\n\n'
                        '형식:\n'
                        '# 📚 강의 통합 노트\n\n'
                        '## 📋 수업 개요\n- 시간, 참가자, 이해도 등\n\n'
                        '## 📖 핵심 내용 정리\n### 1. 주제별 정리\n\n'
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
# 통합 노트 조회
# ══════════════════════════════════════════════════════════

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

        return Response({
            'session_id': session.id,
            'status': note.status,
            'content': note.content if note.status == 'DONE' else '',
            'stats': note.stats,
            'created_at': note.created_at,
        })

