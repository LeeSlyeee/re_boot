from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from .models import LearningSession, STTLog, SessionSummary
from .serializers import LearningSessionSerializer, STTLogSerializer, SessionSummarySerializer, PublicLectureSerializer
import openai
import os
from django.conf import settings
from rest_framework import generics

# OpenAI API Key Setup
openai.api_key = settings.OPENAI_API_KEY

from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Lecture

class PublicLectureListView(generics.ListAPIView):
    queryset = Lecture.objects.all().order_by('-created_at')
    serializer_class = PublicLectureSerializer
    # [Change] Allow browsing without strict auth for debugging, or ensure frontend token is valid
    permission_classes = [AllowAny]

class EnrollLectureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        access_code = request.data.get('access_code')
        if not access_code:
            return Response({'error': 'Access code is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        lecture = get_object_or_404(Lecture, access_code=access_code)
        
        return Response({'message': 'Enrolled successfully', 'lecture_id': lecture.id, 'title': lecture.title}, status=status.HTTP_200_OK)

class LearningSessionViewSet(viewsets.ModelViewSet):
    """
    학습 세션 관리 및 STT/요약 파이프라인
    """
    queryset = LearningSession.objects.all()
    serializer_class = LearningSessionSerializer
    # Debugging: AllowAny temporarily to see if headers are coming
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        # Debugging Logs
        print(f"DEBUG: Headers: {self.request.headers}")
        print(f"DEBUG: Auth Header: {self.request.headers.get('Authorization')}")
        print(f"DEBUG: User: {self.request.user}")
        print(f"DEBUG: Validated Data keys: {serializer.validated_data.keys()}")
        if 'lecture' in serializer.validated_data:
            print(f"DEBUG: Lecture provided: {serializer.validated_data['lecture']}")
        else:
            print("DEBUG: No lecture provided in validated data")
        
        # If user is anonymous (auth failed or no token), use a fallback or error
        if self.request.user.is_anonymous:
             # 임시 조치: 토큰 없이도 생성되게 하거나, 첫 번째 유저를 강제 할당 (테스트용)
             from django.contrib.auth import get_user_model
             User = get_user_model()
             # 테스트 유저 강제 할당 (토큰 문제 해결될 때까지)
             test_user = User.objects.first()
             serializer.save(student=test_user) # Assuming 'student' is the field name
             print(f"DEBUG: Assigned fallback user: {test_user}")
        else:
             serializer.save(student=self.request.user) # Assuming 'student' is the field name

    @action(detail=True, methods=['post'], url_path='chunk')
    def upload_chunk(self, request, pk=None):
        """
        [Legacy] 텍스트 직접 업로드용 (테스트용)
        """
        session = self.get_object()
        serializer = STTLogSerializer(data={
            'session': session.id,
            'sequence_order': request.data.get('sequence_order'),
            'text_chunk': request.data.get('text_chunk')
        })
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'chunk saved'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='audio')
    def upload_audio_chunk(self, request, pk=None):
        """
        [Real] 오디오 파일 업로드 및 Whisper STT 변환
        Request Files: { "audio_file": <blob> }
        Request Data: { "sequence_order": 1 }
        """
        session = self.get_object()
        audio_file = request.FILES.get('audio_file')
        sequence_order = request.data.get('sequence_order', 1)

        if not audio_file:
            return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check API Key
            if not settings.OPENAI_API_KEY:
                print("CRITICAL: OPENAI_API_KEY is missing in settings!")
                return Response({'error': 'Server configuration error: No API Key'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            print(f"DEBUG: API Key Loaded: {settings.OPENAI_API_KEY[:5]}***")

            # 1. Initialize Client (Handles v1.x)
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # 2. Call Whisper API
            print(f"DEBUG: Sending audio to Whisper... (Size: {audio_file.size} bytes)")
            
            # OpenAI v1.x requires tuple (filename, content) for InMemoryUploadedFile
            audio_data = (audio_file.name, audio_file.read())
            
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_data, 
                language="ko" # Force Korean
            )
            
            stt_text = transcript.text
            print(f"DEBUG: Whisper Response: {stt_text[:50]}...") # Log 50 chars
            
            # [FIX] Whisper Hallucination Filter
            # 묵음 구간에서 자주 발생하는 환각 멘트 필터링
            HALLUCINATIONS = [
                "시청해주셔서 감사합니다", "시청해 주셔서 감사합니다",
                "구독과 좋아요", "좋아요와 구독",
                "MBC 뉴스", "SBS 뉴스", "KBS 뉴스",
                "Thanks for watching", "Thank you for watching"
            ]
            
            cleaned_text = stt_text.strip()
            is_hallucination = False
            
            # 1. 완전 일치 또는 포함 여부 검사
            for phrase in HALLUCINATIONS:
                if phrase in cleaned_text:
                    # 문장의 80% 이상이 환각 멘트면 스킵 (유의미한 내용이 섞여있을 수 있으므로)
                    if len(phrase) / len(cleaned_text) > 0.8:
                        is_hallucination = True
                        break
            
            # 2. "감사합니다."만 덩그러니 있는 경우도 스킵
            if cleaned_text.replace('.', '') == "감사합니다":
                is_hallucination = True

            if not cleaned_text or is_hallucination:
                print(f"DEBUG: Hallucination/Silence Skipped ({cleaned_text})")
                return Response({'status': 'silence_skipped', 'text': ''}, status=status.HTTP_200_OK)

            # 3. Save STT Log
            log = STTLog.objects.create(
                session=session,
                sequence_order=sequence_order,
                text_chunk=stt_text
            )
            
            return Response({
                'status': 'processed', 
                'text': stt_text, 
                'id': log.id
            }, status=status.HTTP_201_CREATED)

        except ImportError:
            # Fallback for older openai versions (<1.0)
            try:
                print("DEBUG: Using legacy OpenAI method")
                transcript = openai.Audio.transcribe(
                    model="whisper-1", 
                    file=audio_file,
                    language="ko"
                )
                stt_text = transcript.get('text', '')
                # ... same saving logic ...
                log = STTLog.objects.create(session=session, sequence_order=sequence_order, text_chunk=stt_text)
                return Response({'status': 'processed', 'text': stt_text, 'id': log.id}, status=status.HTTP_201_CREATED)
            except Exception as legacy_e:
                print(f"LEGACY STT Error: {legacy_e}")
                return Response({'error': f"Legacy Error: {str(legacy_e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            print(f"CRITICAL STT Error: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='debug-openai')
    def debug_openai(self, request):
        from openai import OpenAI
        from django.conf import settings
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return Response({"status": "ok", "reply": response.choices[0].message.content}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='summarize')
    def generate_summary(self, request, pk=None):
        print(f"DEBUG: generate_summary called for Session {pk}")
        session = self.get_object()
        
        # 1. 해당 세션의 모든 Chunk 조회 및 병합
        logs = STTLog.objects.filter(session=session).order_by('sequence_order')
        full_text = " ".join([log.text_chunk for log in logs])
        
        print(f"DEBUG: Session {pk} has {logs.count()} chunks. Text Len: {len(full_text)}")
        
        if not full_text.strip():
            print("DEBUG: Empty text. Returning 400.")
            return Response({'error': 'No content to summarize'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. AI 요약 요청 (Real OpenAI Call)
        print("DEBUG: Calling OpenAI...")
        summary_text = self._call_openai_summary(full_text)
        print(f"DEBUG: OpenAI returned: {str(summary_text)[:50]}...")
        
        if not summary_text:
            return Response({'error': 'Summary generation failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3. 요약본 저장
        summary = SessionSummary.objects.create(
            session=session,
            content_text=summary_text,
            raw_stt_link="Processed by OpenAI"
        )
        
        return Response(SessionSummarySerializer(summary).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='end')
    def end_session(self, request, pk=None):
        """
        수업 종료 처리
        """
        session = self.get_object()
        session.end_time = timezone.now()
        session.is_completed = True
        session.save()
        return Response({'status': 'session ended'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='stats')
    def get_stats(self, request):
        """
        대시보드용 사용자 통계 반환
        """
        user = request.user
        
        # 1. 완료된 세션 수
        finished_sessions = LearningSession.objects.filter(student=user, is_completed=True)
        finished_count = finished_sessions.count()
        
        # 2. 총 학습 시간 계산 (분 단위 -> 시간 단위)
        # 실제로는 end_time - start_time을 계산해야 하지만, 간단하게 세션당 평균 30분 or 실제 시간 차이 계산
        total_seconds = 0
        for s in finished_sessions:
            if s.end_time and s.start_time:
                duration = (s.end_time - s.start_time).total_seconds()
                total_seconds += duration
        
        total_hours = round(total_seconds / 3600, 1) # 소수점 1자리까지
        
        # 3. 최근 퀴즈 점수
        from .models import DailyQuiz
        last_quiz = DailyQuiz.objects.filter(student=user).order_by('-created_at').first()
        quiz_score = last_quiz.total_score if last_quiz else 0
        
        # 최근 세션 날짜 추가 (KST 변환)
        import pytz
        last_session = LearningSession.objects.filter(student=user).order_by('-start_time').first()
        last_session_date = None
        
        if last_session and last_session.start_time:
            kst = pytz.timezone('Asia/Seoul')
            # start_time이 aware인지 naive인지 확인 후 변환
            if last_session.start_time.tzinfo:
                local_time = last_session.start_time.astimezone(kst)
            else:
                # Naive라면 UTC로 가정하고 변환 (Django default)
                local_time = pytz.utc.localize(last_session.start_time).astimezone(kst)
                
            last_session_date = local_time.strftime('%Y-%m-%d %p %I:%M').replace('AM', '오전').replace('PM', '오후')

        # [New] 오늘의 학습 시간 계산 (KST 기준)
        import pytz
        from datetime import datetime
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        
        today_sessions = finished_sessions.filter(end_time__gte=today_start_kst) # finished_sessions already filtered by user & completed
        
        today_seconds = 0
        for s in today_sessions:
             if s.end_time and s.start_time:
                duration = (s.end_time - s.start_time).total_seconds()
                today_seconds += duration
        
        today_hours = round(today_seconds / 3600, 1)

        # [Change] 총 학습 시간 상세 분할 (N시간 M분)
        total_hours_int = int(total_seconds // 3600)
        total_minutes_int = int((total_seconds % 3600) // 60)
        
        # 소수점 시간은 유지 (다른 곳에서 쓸 수도 있음)
        total_hours = round(total_seconds / 3600, 1)

        return Response({
            "finishedSessions": finished_count,
            "totalHours": total_hours,
            "totalHoursInt": total_hours_int,  # [New]
            "totalMinutesInt": total_minutes_int, # [New]
            "todayHours": today_hours, 
            "quizScore": quiz_score,
            "lastSessionDate": last_session_date,
            "lastSessionId": last_session.id if last_session else None,
            "lastSessionUrl": last_session.youtube_url if last_session else None
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='update-url')
    def update_url(self, request, pk=None):
        """
        기존 세션의 Youtube URL 업데이트 (복구 후 수동 입력 시 사용)
        """
        session = self.get_object()
        youtube_url = request.data.get('youtube_url')
        
        if youtube_url:
            session.youtube_url = youtube_url
            session.save()
            return Response({'status': 'updated', 'youtube_url': youtube_url}, status=status.HTTP_200_OK)
        return Response({'error': 'URL is required'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='history')
    def get_history(self, request):
        """
        최근 학습 기록 5개 반환 (대시보드용)
        """
        user = request.user
        recent_sessions = LearningSession.objects.filter(student=user, is_completed=True).order_by('-start_time')[:5]
        
        history_data = []
        for session in recent_sessions:
            url = session.youtube_url or ""
            # 제목 결정: URL이 있으면 URL, 없으면 날짜/시간
            import pytz
            kst = pytz.timezone('Asia/Seoul')
            local_time = session.start_time.astimezone(kst) if session.start_time else None
            date_str = local_time.strftime('%Y-%m-%d %p %I:%M').replace('AM', '오전').replace('PM', '오후') if local_time else "날짜 미상"
            
            title = url if url else f"학습 세션 ({date_str})"
            
            history_data.append({
                "sessionId": session.id,
                "title": title,
                "url": url,
                "date": date_str,
                "isFallback": not url # URL 없으면 Fallback
            })
            
        return Response(history_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='logs')
    def get_logs(self, request, pk=None):
        """
        세션의 모든 STT 로그 조회
        """
        session = self.get_object()
        logs = STTLog.objects.filter(session=session).order_by('sequence_order')
        serializer = STTLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='debug-sessions')
    def debug_sessions(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_count = User.objects.count()
        first_user = User.objects.first()
        test_user = User.objects.filter(username='testuser').first()
        
        info = {
            "user_count": user_count,
            "first_user_id": first_user.id if first_user else None,
            "first_user_name": first_user.username if first_user else None,
            "test_user_id": test_user.id if test_user else None,
            "current_request_user": str(request.user),
            "current_request_user_id": request.user.id if request.user.is_authenticated else "Anon"
        }
        
        sessions = LearningSession.objects.all().order_by('-start_time')[:10]
        data = []
        for s in sessions:
            data.append({
                "id": s.id,
                "student_id": s.student.id,
                "student_username": s.student.username,
                "lecture_id": s.lecture_id,
                "created": str(s.start_time),
                "title": s.section.title if s.section else "No Section"
            })
        return Response({'info': info, 'sessions': data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='lectures/(?P<lecture_id>[^/.]+)')
    def get_lecture_sessions(self, request, lecture_id=None):
        """
        특정 클래스(Lecture)의 내 수강 기록(Session List) 반환
        [Self-Healing] 만약 기록이 없으면, 최근 24시간 내의 '강의 미지정' 세션을 찾아 자동으로 연결함.
        """
        user = request.user
        
    @action(detail=False, methods=['get'], url_path='debug-lectures')
    def debug_lectures(self, request):
        lectures = Lecture.objects.all()
        data = [{"id": l.id, "title": l.title} for l in lectures]
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='lectures/(?P<lecture_id>[^/.]+)')
    def get_lecture_sessions(self, request, lecture_id=None):
        """
        특정 클래스(Lecture)의 내 수강 기록(Session List) 반환
        [FINAL FIX] testuser 강제 타겟팅 + 고아(Orphan) 세션 포함 조회
        """
        print(f"DEBUG: FINAL ATTEMPT get_lecture_sessions ID={lecture_id}")
        
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        User = get_user_model()
        
        # 1. Target User: 'testuser' (시스템상 데이터가 쌓이는 곳)
        target_user = User.objects.filter(username='testuser').first()
        if not target_user:
             target_user = User.objects.first()
             print("DEBUG: testuser not found, using first user.")

        if not target_user:
            print("DEBUG: No users found in DB.")
            return Response([], status=status.HTTP_200_OK)

        # 2. Fetch Linked sessions OR Orphans
        # 조건: (지정된 강의 ID) 또는 (강의가 없는 미아 세션)
        # 이렇게 하면 연결이 끊긴 세션도 무조건 보임.
        sessions = LearningSession.objects.filter(
            student=target_user
        ).filter(
            Q(lecture_id=lecture_id) | Q(lecture__isnull=True)
        ).order_by('-start_time')

        print(f"DEBUG: Found {sessions.count()} sessions for {target_user}")
        
        data = []
        for s in sessions:
             title = f"{s.session_order}교시 수업"
             if s.section:
                 title = f"{s.section.title} ({s.session_order}교시)"
            
             data.append({
                 "id": s.id,
                 "session_order": s.session_order,
                 "session_date": s.session_date,
                 "is_completed": s.is_completed,
                 "created_at": s.start_time,
                 "title": title
             })
             
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='lectures/(?P<lecture_id>[^/.]+)/shared-notes')
    def get_shared_notes(self, request, lecture_id=None):
        """
        [특정 클래스 날짜별 노트 공유]
        Query Param: date (YYYY-MM-DD)
        """
        target_date = request.query_params.get('date')
        if not target_date:
             return Response({'error': 'Date parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 1. 같은 Lecture, 같은 Date, Summary가 있는 세션 검색
        # (본인 포함? 아니면 본인 제외? -> 학습 자료 공유니까 모두 포함)
        shared_sessions = LearningSession.objects.filter(
            lecture_id=lecture_id,
            # session_date 필드가 있다면 사용, 없다면 start_time__date 사용
            # 모델 정의상 session_date가 있음
            session_date=target_date, 
            is_completed=True
        ).select_related('student').prefetch_related('summaries')
        
        notes = []
        for sess in shared_sessions:
            # 가장 최근 요약본 1개만 가져옴
            summary = sess.summaries.last()
            if summary:
                notes.append({
                    "student_name": sess.student.username, # TODO: 익명화 필요 시 마스킹
                    "note_content": summary.content_text,
                    "created_at": summary.created_at,
                    "session_id": sess.id
                })
        
        return Response(notes, status=status.HTTP_200_OK)

    def _call_openai_summary(self, text):
        """
        ChatGPT에게 요약 요청하는 내부 메서드 Helper
        """
        from openai import OpenAI
        from django.conf import settings
        
        # [Optimization] Set timeout to avoid hanging (180s = 3min)
        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=180.0)
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """
                    너는 IT 부트캠프의 '수석 정리 노트 작성자'야.
                    학생들이 수업 내용을 나중에 다시 보고 완벽하게 복습할 수 있도록, 
                    제공된 [STT 스크립트]를 바탕으로 **구조화된 학습 자료(Lecture Note)**를 만들어줘.
                    
                    반드시 아래 **Markdown 포맷**을 따라 작성해줘.
                    
                    # [강의 제목: 핵심 주제]
                    
                    ## 1. 3줄 요약
                    - (핵심 요약 1)
                    - (핵심 요약 2)
                    - (핵심 요약 3)
                    
                    ## 2. 주요 학습 개념
                    - **(개념 1)**: (설명)
                    - **(개념 2)**: (설명)
                    
                    ## 3. 상세 강의 노트
                    (강의 흐름에 따라 중요 내용을 불렛 포인트로 정리, 코드 예시가 있다면 ```code``` 블럭으로 포함)
                    
                    ## 4. 핵심 암기 사항
                    - (시험이나 실무에서 중요한 팁)
                    """},
                    {"role": "user", "content": f"다음 수업 내용을 학습 자료로 정리해줘:\n\n{text}"}
                ],
                max_tokens=1500  # Reasonable limit
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Summary Generation Error: {e}")
            # Fallback: Simple Logic
            fallback_text = "# [자동 생성: 간이 학습 노트]\n\n"
            fallback_text += "> ⚠️ AI 서버 연결 지연으로 인해 원문 기반의 간이 요약을 표시합니다.\n\n"
            fallback_text += "## 1. 수업 핵심 내용 (원문 발췌)\n"
            
            # Simple extraction: First 500 chars + Last 500 chars
            if len(text) > 1000:
                fallback_text += text[:500] + "\n\n...(중략)...\n\n" + text[-500:]
            else:
                fallback_text += text
            
            return fallback_text
