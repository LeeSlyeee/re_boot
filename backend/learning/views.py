from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db.models import Q # Added Q
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

class MyLectureListView(generics.ListAPIView):
    serializer_class = PublicLectureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.enrolled_lectures.all().order_by('-created_at')

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
    # Require authentication for learning sessions
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # print(f"DEBUG: get_queryset user={user} action={self.action} method={self.request.method}")
        
        # [Security]
        # 상세 조회(retrieve) 및 로그 조회(get_logs) 시에는 
        # '같은 강의 수강생의 완료된 세션'을 열어줌. (보충 학습용)
        # 수정/삭제/목록조회 등은 오직 '내 세션'만 가능.
        if self.action in ['retrieve', 'get_logs', 'logs']: # 'logs' added just in case
            return LearningSession.objects.filter(
                Q(student=user) | 
                Q(lecture__students=user, is_completed=True)
            ).distinct()
            
        return LearningSession.objects.filter(student=user)

    def perform_create(self, serializer):
        # Strictly associate with the authenticated user
        serializer.save(student=self.request.user)

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
        print(f"--- [Audio Upload Start] Session: {pk} ---")
        session = self.get_object()
        audio_file = request.FILES.get('audio_file')
        sequence_order = request.data.get('sequence_order', 1)

        if not audio_file:
            print("❌ Error: No audio file provided.")
            return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check API Key
            if not settings.OPENAI_API_KEY:
                print("❌ CRITICAL: OPENAI_API_KEY is missing!")
                return Response({'error': 'Server configuration error: No API Key'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 1. Initialize Client
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # [DEBUG LOGGING]
            with open("debug_stt.log", "a") as f:
                f.write(f"[{sequence_order}] Size: {audio_file.size}, Type: {audio_file.content_type}\n")

            # [CONTEXT IMPROVEMENT] Use last 3 logs as prompt to guide Whisper
            # This significantly reduces "silence hallucinations" by providing context.
            previous_context = ""
            # Must evaluate QuerySet to list because reversed() on sliced QuerySet is not supported by DB
            recent_logs = list(STTLog.objects.filter(session=session).order_by('-sequence_order')[:3])
            
            if recent_logs:
                # Reverse to get chronological order: Oldest -> Newest
                # recent_logs is now a list, so reversed() is safe
                previous_context = " ".join([log.text_chunk for log in reversed(recent_logs)])
            
            # Limit prompt length (OpenAI limit is ~224 tokens, keep it safe)
            # Python slice handles chars, safe for unicode
            if len(previous_context) > 200:
                previous_context = previous_context[-200:]

            # 2. Prepare Audio for Whisper
            file_name = audio_file.name or "chunk.webm"
            audio_data = (file_name, audio_file.read(), audio_file.content_type or "audio/webm")

            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_data, 
                language="ko",
                response_format="verbose_json", # [CRITICAL] Request Metadata
                prompt=f"이것은 강의 자막입니다. 이전 내용: {previous_context}", 
            )
            
            # verbose_json returns an object with 'text' and 'segments'
            stt_text = transcript.text
            segments = getattr(transcript, 'segments', [])
            
            # [SILENCE DETECTION] Use Whisper's internal confidence
            if segments:
                # Use the first segment's probability (since we send small chunks)
                first_seg = segments[0]
                no_speech_prob = getattr(first_seg, 'no_speech_prob', 0)
                avg_logprob = getattr(first_seg, 'avg_logprob', 0)
                
                with open("debug_stt.log", "a") as f:
                    f.write(f"[{sequence_order}] PROBS: NoSpeech={no_speech_prob:.4f}, LogProb={avg_logprob:.4f}\n")

                # If Whisper is 50% sure it's silence, trust it.
                if no_speech_prob > 0.5:
                     with open("debug_stt.log", "a") as f:
                         f.write(f"⚠️ Filtered by NoSpeechProb: {no_speech_prob}\n")
                     return Response({'status': 'silence_skipped', 'text': '', 'reason': 'High No Speech Prob'}, status=status.HTTP_200_OK)

            with open("debug_stt.log", "a") as f:
                f.write(f"[{sequence_order}] RAW WHISPER: {stt_text}\n")
            
            print(f"📝 Whisper Raw Output: [{stt_text}]")
            
            # [CRITICAL FIX] Hallucination & Valid Content Filter
            # 1. Hallucination List (Updated from user logs)
            HALLUCINATIONS = [
                "시청해주셔서 감사합니다", "시청해 주셔서 감사합니다",
                "구독과 좋아요", "좋아요와 구독", "구독&좋아요", "♥", 
                "MBC 뉴스", "SBS 뉴스", "KBS 뉴스", "YTN 뉴스",
                "Thanks for watching", "Thank you for watching",
                "Subtitles by", "자막 제작", "제작:", "한글자막", "by neD",
                "스크립트의 내용을 받아적은 스크립트입니다",
                "자막 제공 및 광고는", "KickSubs.com",
                "UpTitle", "uptitle.co.kr", 
                "영상편집 및 자막이 필요하면", 
                "댓글에 링크를 적어줘", 
                "뷔 뷔 뷔 뷔", "ㅋㅋㅋㅋ",
                "매주 일요일 업로드됩니다", 
                "에이에이에이에이", "Paloalto",
                "오늘도 봐주셔서 감사합니다", "유료광고", "투모로우바이투게더"
            ]
            
            cleaned_text = stt_text.strip()
            is_hallucination = False
            skip_reason = ""

            # 2. Empty Check
            if not cleaned_text:
                return Response({'status': 'silence_skipped', 'text': '', 'reason': 'Empty'}, status=status.HTTP_200_OK)

            # [NEW] Prompt Echo Check (Prevent looping previous context)
            # If current text is just a subset of previous context, it's a loop.
            if len(cleaned_text) > 5 and cleaned_text in previous_context:
                 is_hallucination = True
                 skip_reason = "Prompt Echo Loop"

            # [NEW] Internal Repetition Check (e.g., "Hello Hello")
            # Simple check: if first half equals second half
            mid = len(cleaned_text) // 2
            if len(cleaned_text) > 10 and cleaned_text[:mid].strip() == cleaned_text[mid:].strip():
                 is_hallucination = True
                 skip_reason = "Internal Repetition"

            # 3. Phrase Matching (Keyword Ban)
            if not is_hallucination:
                for phrase in HALLUCINATIONS:
                    # Remove spaces for robust checking
                    if phrase.replace(" ", "").lower() in cleaned_text.replace(" ", "").lower():
                        is_hallucination = True
                        skip_reason = f"Banned Phrase: {phrase}"
                        break
            
            # 4. Strict Repetition Filter (Prevent Looping)
            if not is_hallucination:
                # Check last 3 logs
                recent_logs = STTLog.objects.filter(session=session).order_by('-sequence_order')[:3]
                
                for log in recent_logs:
                    prev = log.text_chunk.strip()
                    curr = cleaned_text
                    
                    # A. Exact Match
                    if prev == curr:
                        is_hallucination = True
                        skip_reason = "Exact Duplicate"
                        break
                    
                    # B. Jaccard Similarity for longer text
                    set_prev = set(prev.split())
                    set_curr = set(curr.split())
                    if len(set_curr) > 0:
                        overlap = len(set_prev & set_curr) / len(set_curr)
                        if overlap > 0.9: # 90% word overlap (Stricter)
                            is_hallucination = True
                            skip_reason = "High Word Overlap"
                            break

                    # C. Substring Inclusion (Short Phrase Echo)
                    # If current (short) is contained in previous (long), it's likely an echo
                    if len(curr) < 20 and len(curr) < len(prev) and curr in prev:
                        is_hallucination = True
                        skip_reason = "Short Substring Echo"
                        break

            if is_hallucination:
                with open("debug_stt.log", "a") as f:
                    f.write(f"⚠️ Filtered: '{cleaned_text}' | Reason: {skip_reason}\n")
                print(f"⚠️ Filtered: '{cleaned_text}' | Reason: {skip_reason}")
                return Response({'status': 'silence_skipped', 'text': '', 'reason': skip_reason}, status=status.HTTP_200_OK)

            # 5. Save STT Log
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

        except Exception as e:
            with open("debug_stt.log", "a") as f:
                f.write(f"ERROR: {str(e)}\n")
            print(f"❌ CRITICAL STT Error: {e}")
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
        
        # [NEW] 4. RAG Indexing Trigger
        try:
            from .rag import RAGService
            rag = RAGService()
            rag.index_session(session.id)
            print(f"✅ RAG Indexed Session {session.id}")
        except Exception as e:
            print(f"⚠️ RAG Indexing Failed: {e}")
        
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
        [Change] 진행 중인 세션도 포함하여 최근 활동 내역 표시
        """
        user = request.user
        
        user = request.user

        # completed filter removed to show all recent activity
        
        recent_sessions = LearningSession.objects.filter(student=user).order_by('-start_time')[:5]
        
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


        
    @action(detail=False, methods=['get'], url_path='debug-lectures')
    def debug_lectures(self, request):
        lectures = Lecture.objects.all()
        data = [{"id": l.id, "title": l.title} for l in lectures]
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='lectures/(?P<lecture_id>[^/.]+)')
    def get_lecture_sessions(self, request, lecture_id=None):
        """
        특정 클래스(Lecture)의 내 수강 기록(Session List) 반환
        """
        user = request.user
        
        # Fetch sessions for this lecture & this user
        sessions = LearningSession.objects.filter(
            student=user,
            lecture_id=lecture_id
        ).order_by('-start_time')

        print(f"DEBUG: Found {sessions.count()} sessions for {user}")
        
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

    @action(detail=False, methods=['get'], url_path='lectures/(?P<lecture_id>[^/.]+)/missed')
    def get_missed_lectures(self, request, lecture_id=None):
        """
        [보충 학습 기능]
        내가 참여하지 않았지만, 다른 학생들이 수강한 날짜 목록 반환
        """
        user = request.user
        
        # [Security] Enrollment Check
        lecture = get_object_or_404(Lecture, id=lecture_id)
        if not lecture.students.filter(id=user.id).exists():
             return Response({'error': 'You are not enrolled in this lecture.'}, status=status.HTTP_403_FORBIDDEN)
        
        # 1. 해당 강의의 모든 세션 (다른 학생들 포함)
        all_sessions = LearningSession.objects.filter(
            lecture_id=lecture_id,
            is_completed=True
        ).exclude(student=user) # 내 세션은 제외 (이미 들은 건 논외)

        # 2. 날짜별 그룹화 (Django ORM Group By Date)
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        
        # 날짜별 세션 수 카운트
        missed_dates = all_sessions.annotate(
            date=TruncDate('start_time')
        ).values('date').annotate(
            peer_count=Count('id')
        ).order_by('-date')

        # 3. 내가 이미 수강한 날짜 확인
        my_dates = LearningSession.objects.filter(
            student=user,
            lecture_id=lecture_id
        ).annotate(
            date=TruncDate('start_time')
        ).values_list('date', flat=True)
        
        my_dates_set = set(my_dates)

        results = []
        for item in missed_dates:
            d = item['date']
            if d not in my_dates_set:
                # 4. 해당 날짜의 대표 세션 ID 찾기 (가장 긴 요약본음 가진 세션 등)
                # 여기서는 간단히 첫 번째 세션 ID 반환
                rep_session = LearningSession.objects.filter(
                    lecture_id=lecture_id,
                    start_time__date=d,
                    is_completed=True
                ).exclude(student=user).first()
                
                if rep_session:
                    results.append({
                        "date": d,
                        "title": f"[보충] {d.strftime('%Y-%m-%d')} 수업",
                        "peer_count": item['peer_count'],
                        "representative_session_id": rep_session.id
                    })

        return Response(results, status=status.HTTP_200_OK)

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
        from openai import OpenAI
        from django.conf import settings
        
        # [Optimization] Set timeout to avoid hanging (180s = 3min)
        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=180.0)
        
        try:
            # System prompt defined as a variable to avoid indentation issues
            system_prompt = (
                "너는 IT 부트캠프의 '수석 정리 노트 작성자'야.\n"
                "학생들이 수업 내용을 나중에 다시 보고 완벽하게 복습할 수 있도록, \n"
                "제공된 [STT 스크립트]를 바탕으로 **구조화된 학습 자료(Lecture Note)**를 만들어줘.\n\n"
                "반드시 아래 **Markdown 포맷**을 따라 작성해줘.\n\n"
                "# [강의 제목: 핵심 주제]\n\n"
                "## 1. 3줄 요약\n"
                "- (핵심 요약 1)\n"
                "- (핵심 요약 2)\n"
                "- (핵심 요약 3)\n\n"
                "## 2. 주요 학습 개념\n"
                "- **(개념 1)**: (설명)\n"
                "- **(개념 2)**: (설명)\n\n"
                "## 3. 상세 강의 노트\n"
                "(강의 흐름에 따라 중요 내용을 불렛 포인트로 정리, 코드 예시가 있다면 ```code``` 블럭으로 포함)\n\n"
                "## 4. 핵심 암기 사항\n"
                "- (시험이나 실무에서 중요한 팁)\n\n"
                "[🚨 중요 필터링 규칙]\n"
                "1. **잡담 및 소음 제거**: 강의 내용과 무관한 농담, 잡담, 주변 소음, 혼잣말은 완벽하게 제외할 것.\n"
                "2. **학생 질문 분리**: 강의자(Instructor)의 설명 위주로 요약하고, 청중(학생)의 단순 질문이나 웅성거림은 노트에 포함하지 말 것.\n"
                "3. **문맥 파악**: '잠시만요', '들리시나요', '네네' 같은 무의미한 추임새는 전부 삭제하고, 핵심 정보만 남길 것."
            )

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 수업 내용을 학습 자료로 정리해줘:\n\n{text}"}
                ],
                max_tokens=1500
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

    # ──────────────────────────────────────────
    # [NEW] PDF 내보내기 API
    # ──────────────────────────────────────────
    @action(detail=True, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request, pk=None):
        """
        세션의 요약본을 PDF로 변환하여 다운로드
        - SessionSummary의 Markdown 텍스트를 HTML로 변환 후 PDF 생성
        """
        import io
        import re
        from django.http import HttpResponse

        session = self.get_object()
        summaries = SessionSummary.objects.filter(session=session).order_by('created_at')
        
        if not summaries.exists():
            return Response({'error': '요약본이 없습니다. 먼저 요약을 생성해주세요.'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        # 모든 요약본을 하나로 합침
        combined_text = ""
        for idx, summary in enumerate(summaries):
            if idx > 0:
                combined_text += "\n\n---\n\n"
            combined_text += summary.content_text
        
        # Markdown → Simple HTML 변환 (외부 라이브러리 없이 기본 변환)
        def md_to_html(md_text):
            lines = md_text.split('\n')
            html_lines = []
            in_code_block = False
            
            for line in lines:
                # Code Block
                if line.strip().startswith('```'):
                    if in_code_block:
                        html_lines.append('</pre>')
                        in_code_block = False
                    else:
                        html_lines.append('<pre style="background:#f5f5f5;padding:12px;border-radius:6px;font-size:13px;overflow-x:auto;">')
                        in_code_block = True
                    continue
                
                if in_code_block:
                    html_lines.append(line)
                    continue
                
                # Headers
                if line.startswith('# '):
                    html_lines.append(f'<h1 style="color:#1a1a2e;border-bottom:2px solid #4facfe;padding-bottom:8px;">{line[2:]}</h1>')
                elif line.startswith('## '):
                    html_lines.append(f'<h2 style="color:#333;margin-top:24px;">{line[3:]}</h2>')
                elif line.startswith('### '):
                    html_lines.append(f'<h3 style="color:#555;">{line[4:]}</h3>')
                # Blockquote
                elif line.startswith('> '):
                    html_lines.append(f'<blockquote style="border-left:3px solid #4facfe;padding-left:12px;color:#666;margin:8px 0;">{line[2:]}</blockquote>')
                # Horizontal rule
                elif line.strip() == '---':
                    html_lines.append('<hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">')
                # Bullet points
                elif line.strip().startswith('- '):
                    content = line.strip()[2:]
                    # Bold text
                    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
                    html_lines.append(f'<div style="padding:3px 0 3px 20px;">• {content}</div>')
                # Empty line
                elif line.strip() == '':
                    html_lines.append('<br>')
                # Normal paragraph
                else:
                    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                    content = re.sub(r'`(.+?)`', r'<code style="background:#e8e8e8;padding:2px 4px;border-radius:3px;font-size:13px;">\1</code>', content)
                    html_lines.append(f'<p style="margin:4px 0;line-height:1.6;">{content}</p>')
            
            return '\n'.join(html_lines)
        
        content_html = md_to_html(combined_text)
        
        # 세션 정보
        import pytz
        kst = pytz.timezone('Asia/Seoul')
        session_date = session.start_time.astimezone(kst).strftime('%Y년 %m월 %d일') if session.start_time else '날짜 미상'
        section_title = session.section.title if session.section else '자율 학습'
        
        # Full HTML Document
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif;
                    max-width: 800px; margin: 0 auto; padding: 40px;
                    color: #333; line-height: 1.7;
                }}
                .header {{
                    text-align: center; margin-bottom: 40px; padding-bottom: 20px;
                    border-bottom: 2px solid #4facfe;
                }}
                .header h1 {{ color: #1a1a2e; margin: 0; font-size: 24px; }}
                .header p {{ color: #888; margin: 8px 0 0; font-size: 14px; }}
                .footer {{
                    margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;
                    text-align: center; color: #aaa; font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📝 Re:Boot 학습 노트</h1>
                <p>{section_title} | {session_date} | {session.session_order}교시</p>
            </div>
            {content_html}
            <div class="footer">
                Re:Boot Career Build-up Platform | AI 기반 학습 요약 자동 생성
            </div>
        </body>
        </html>
        """
        
        # HTML을 직접 다운로드 가능한 형태로 반환 (브라우저에서 인쇄→PDF 가능)
        response = HttpResponse(html_content, content_type='text/html; charset=utf-8')
        filename = f"ReBootNote_{session.id}_{session_date.replace(' ', '')}.html"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

    # ──────────────────────────────────────────
    # [NEW] 노트 기능 (사용자 메모 추가)
    # ──────────────────────────────────────────
    @action(detail=True, methods=['get', 'post'], url_path='note')
    def note(self, request, pk=None):
        """
        GET: 세션의 사용자 메모를 조회
        POST: 세션에 사용자 메모를 저장
        """
        session = self.get_object()

        if request.method == 'GET':
            latest_summary = session.summaries.last()
            note_content = ''
            if latest_summary:
                note_marker = "\n\n---\n\n## 📌 나의 메모\n"
                if note_marker in latest_summary.content_text:
                    note_content = latest_summary.content_text.split(note_marker)[1]
            return Response({
                'has_note': bool(note_content),
                'note': note_content,
                'summary_id': latest_summary.id if latest_summary else None
            })

        # POST
        note_text = request.data.get('note', '')
        if not note_text:
            return Response({'error': '메모 내용이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        latest_summary = session.summaries.last()

        if latest_summary:
            note_marker = "\n\n---\n\n## 📌 나의 메모\n"
            if note_marker in latest_summary.content_text:
                base_content = latest_summary.content_text.split(note_marker)[0]
                latest_summary.content_text = base_content + note_marker + note_text
            else:
                latest_summary.content_text += note_marker + note_text
            latest_summary.save()
            return Response({
                'status': 'saved',
                'summary_id': latest_summary.id,
                'content': latest_summary.content_text
            })
        else:
            summary = SessionSummary.objects.create(
                session=session,
                content_text=f"## 📌 나의 메모\n{note_text}",
                raw_stt_link="User Note"
            )
            return Response({
                'status': 'created',
                'summary_id': summary.id,
                'content': summary.content_text
            }, status=status.HTTP_201_CREATED)

from .models import Syllabus, LearningObjective, StudentChecklist, Lecture
from .serializers import SyllabusSerializer

class ChecklistViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # GET /api/learning/lectures/<lecture_id>/checklist/
    # DRF Router will allow: /api/learning/checklist/
    # But we want specific lecture context. 
    # Use: /api/learning/lectures/<lecture_id>/checklist/ if registered under lectures
    # OR: /api/learning/checklists/?lecture_id=<id>
    
    # Let's use custom action on ViewSet or standalone ViewSet
    # Here we use ViewSet with manual route or query param
    
    def list(self, request):
        lecture_id = request.query_params.get('lecture_id')
        if not lecture_id:
            return Response({"error": "lecture_id required"}, status=400)
            
        lecture = get_object_or_404(Lecture, id=lecture_id)
        
        # Check enrollment
        if not lecture.students.filter(id=request.user.id).exists() and lecture.instructor != request.user:
             return Response({"error": "Not enrolled"}, status=403)

        syllabi = Syllabus.objects.filter(lecture=lecture)
        serializer = SyllabusSerializer(syllabi, many=True, context={'request': request})
        return Response(serializer.data)

    # POST /api/learning/checklist/<objective_id>/toggle/
    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        objective = get_object_or_404(LearningObjective, id=pk)
        
        lecture = objective.syllabus.lecture
        if not lecture.students.filter(id=request.user.id).exists():
             return Response({"error": "Not enrolled"}, status=403)

        checklist, created = StudentChecklist.objects.get_or_create(student=request.user, objective=objective)
        checklist.is_checked = not checklist.is_checked
        checklist.save()
        
        return Response({"id": objective.id, "is_checked": checklist.is_checked})

    # GET /api/learning/checklist/analyze/?lecture_id=<id>
    # [Dynamic Re-routing Engine]
    @action(detail=False, methods=['get'])
    def analyze(self, request):
        lecture_id = request.query_params.get('lecture_id')
        if not lecture_id:
            return Response({"error": "lecture_id required"}, status=400)
            
        lecture = get_object_or_404(Lecture, id=lecture_id)
        
        # 1. Calculate Progress
        total_objectives = LearningObjective.objects.filter(syllabus__lecture=lecture).count()
        if total_objectives == 0:
            return Response({"status": "clean", "progress": 0, "message": "아직 학습 목표가 없습니다."})

        checked_count = StudentChecklist.objects.filter(
            student=request.user, 
            objective__syllabus__lecture=lecture, 
            is_checked=True
        ).count()
        
        progress = (checked_count / total_objectives) * 100
        
        # 2. Determine Status (Simple Heuristic for MVP)
        # In real-world, we would check 'time passing' vs 'progress'
        status = "good"
        recommendation = None
        
        if progress < 30:
            status = "critical"
            recommendation = {
                "type": "catch_up",
                "title": "🚨 경로 이탈 위험!",
                "message": "진도율이 너무 낮습니다 (30% 미만). AI가 핵심 요약 코스로 경로를 재설정할까요?",
                "action": "압축 코스 생성"
            }
        elif progress < 60:
            status = "warning"
            recommendation = {
                "type": "review",
                "title": "⚠️ 학습 지연 감지",
                "message": "계획보다 뒤쳐지고 있습니다. 놓친 핵심 개념만 빠르게 훑어보세요.",
                "action": "빠른 복습 하기"
            }
        else:
            status = "good"
            recommendation = {
                "type": "keep_going",
                "title": "✅ 순항 중",
                "message": "훌륭합니다! 현재 속도를 유지하세요.",
                "action": None
            }
            
        return Response({
            "progress": round(progress, 1),
            "status": status,
            "recommendation": recommendation
        })

    # POST /api/learning/checklist/recovery_plan/
    # [Dynamic Re-routing Action]
    @action(detail=False, methods=['post'])
    def recovery_plan(self, request):
        lecture_id = request.data.get('lecture_id')
        if not lecture_id:
            return Response({"error": "lecture_id required"}, status=400)
            
        lecture = get_object_or_404(Lecture, id=lecture_id)
        
        # 1. Collect unfinished objectives
        unfinished_objectives = LearningObjective.objects.filter(
            syllabus__lecture=lecture
        ).exclude(
            student_checks__student=request.user, 
            student_checks__is_checked=True
        )
        
        if not unfinished_objectives.exists():
            return Response({"message": "모든 학습 목표를 달성했습니다! 복구할 내용이 없습니다."})
            
        # 2. Format for AI Prompt
        objective_texts = "\n".join([f"- {obj.content}" for obj in unfinished_objectives])
        
        # 3. Call OpenAI
        from django.conf import settings
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        system_prompt = (
            "당신은 '학습 경로 재설계 전문가'입니다.\n"
            "학생이 놓친 학습 목표들을 바탕으로, 단기간에 캐치업할 수 있는 '핵심 압축 가이드'를 작성해주세요.\n"
            "반드시 아래 Markdown 형식을 따라주세요:\n\n"
            "# 🚀 3분 압축 복구 플랜\n\n"
            "## 1. 지금 꼭 알아야 할 핵심 개념\n"
            "(놓친 항목들의 핵심 정의를 3줄 요약)\n\n"
            "## 2. 실무 적용 포인트\n"
            "(해당 개념이 왜 중요한지, 어떻게 쓰이는지 간단 설명)\n\n"
            "## 3. 추천 학습 순서\n"
            "1. (가장 먼저 봐야 할 것)\n"
            "2. (그 다음 순서)\n"
        )
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음은 학생이 아직 학습하지 못한 목표들입니다. 이를 위한 복구 플랜을 짜주세요:\n\n{objective_texts}"}
                ],
                max_tokens=1000
            )
            recovery_content = response.choices[0].message.content
            
            return Response({
                "status": "success",
                "recovery_plan": recovery_content,
                "unfinished_count": unfinished_objectives.count()
            })
            
        except Exception as e:
            print(f"OPENAI API Error: {str(e)}")
            # Fallback for Demo/Error cases
            fallback_plan = (
                "# 🚀 [임시] 3분 압축 복구 플랜\n"
                "(AI 서비스 연결이 원활하지 않아 자동 생성된 임시 플랜입니다.)\n\n"
                "## 1. 놓친 핵심 개념 요약\n"
            )
            for obj in unfinished_objectives[:3]:
                 fallback_plan += f"- **{obj.content}**: 이 개념은 반드시 숙지해야 합니다.\n"
            
            fallback_plan += "\n## 2. 추천 학습 경로\n1. 공식 문서 빠르게 훑어보기\n2. 예제 코드 실행해보기\n"
            
            return Response({
                "status": "success",
                "recovery_plan": fallback_plan,
                "unfinished_count": unfinished_objectives.count(),
                "is_fallback": True
            })
