"""
학습 세션 관리 Views: LearningSessionViewSet
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import LearningSession, STTLog, SessionSummary, Lecture, DailyQuiz
from .models.live import LiveParticipant, LiveSTTLog, LiveSessionNote
from .serializers import LearningSessionSerializer, STTLogSerializer, SessionSummarySerializer

import openai
import os
import logging
from logging.handlers import RotatingFileHandler

# Re-export for backward compatibility (urls.py imports from .views)
from .lecture_views import PublicLectureListView, MyLectureListView, EnrollLectureView  # noqa: F401
from .checklist_views import ChecklistViewSet  # noqa: F401

# OpenAI API Key Setup
openai.api_key = settings.OPENAI_API_KEY

# STT 디버그 로거 설정 (RotatingFileHandler: 5MB 제한, 최대 3파일)
stt_logger = logging.getLogger('stt_debug')
if not stt_logger.handlers:
    handler = RotatingFileHandler('debug_stt.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
    stt_logger.addHandler(handler)
    stt_logger.setLevel(logging.DEBUG)


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

    def _get_linked_live_session(self, learning_session):
        """
        LearningSession에 연결된 LiveSession을 찾는다.
        LiveParticipant.learning_session FK 역참조 사용.
        """
        participant = LiveParticipant.objects.filter(
            learning_session=learning_session
        ).select_related('live_session').first()
        if participant:
            return participant.live_session
        return None

    def retrieve(self, request, *args, **kwargs):
        """
        [Override] 세션 상세 조회 시 연결된 라이브 세션 데이터를 자동 감지하여 포함
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        # 라이브 세션 연결 감지
        live_session = self._get_linked_live_session(instance)
        if live_session:
            data['is_live_session'] = True
            data['live_session_id'] = live_session.id
            data['live_session_code'] = live_session.session_code
            data['live_session_title'] = live_session.title

            # 라이브 요약 노트 (LiveSessionNote)
            try:
                note = live_session.note  # OneToOneField reverse
                if note and note.status == 'DONE' and note.content:
                    data['latest_summary'] = note.content
            except LiveSessionNote.DoesNotExist:
                pass
        else:
            data['is_live_session'] = False

        return Response(data)

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
            stt_logger.debug(f"[{sequence_order}] Size: {audio_file.size}, Type: {audio_file.content_type}")

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

            # [UPGRADE] gpt-4o-transcribe: GPT-4o 언어 이해력 결합으로 환각 구조적 억제
            # 오디오 크기가 너무 작으면 (8KB 미만) 침묵으로 간주
            if audio_file.size < 8000:
                stt_logger.debug(f"[{sequence_order}] Skipped: audio too small ({audio_file.size} bytes)")
                return Response({'status': 'silence_skipped', 'text': '', 'reason': f'Audio too small ({audio_file.size}B)'}, status=status.HTTP_200_OK)

            transcript = client.audio.transcriptions.create(
                model="gpt-4o-transcribe", 
                file=audio_data, 
                # [FIX] 언어 자동 감지 (한국어/영어 모두 지원)
                prompt=f"이것은 한국어/영어 IT 부트캠프 강의 자막입니다. 이전 내용: {previous_context}" if previous_context else "이것은 한국어/영어 IT 부트캠프 강의 자막입니다.",
            )
            
            stt_text = transcript.text

            stt_logger.debug(f"[{sequence_order}] RAW GPT-4o-TRANSCRIBE: {stt_text}")
            print(f"📝 GPT-4o-Transcribe Output: [{stt_text}]")
            
            # [CRITICAL FIX] Hallucination & Valid Content Filter (v2 강화)
            # 1. Hallucination List (확장됨)
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
                "오늘도 봐주셔서 감사합니다", "유료광고", "투모로우바이투게더",
                "다음 영상에서 만나요", "좋아요 부탁드립니다",
                "채널 구독 부탁드립니다", "알림 설정",
                "BGM", "Outro", "소스 음악",
                "www.", "http", ".com", ".kr",
                "Amara.org", "자막 제공",
                # [FIX] Whisper 프롬프트 에코 방지
                "이것은 한국어", "이것은 한국어/영어",
                "IT 부트캠프 강의 자막입니다",
                "부트캠프 강의 자막", "이전 내용:",
            ]
            
            cleaned_text = stt_text.strip()
            is_hallucination = False
            skip_reason = ""

            # 2. Empty Check
            if not cleaned_text:
                return Response({'status': 'silence_skipped', 'text': '', 'reason': 'Empty'}, status=status.HTTP_200_OK)

            # [NEW] 2.5. 너무 짧은 무의미 텍스트 필터 (5자 이하 한/영 단독)
            import re as _re
            if len(cleaned_text) <= 5:
                # 의미있는 단어 (예: "변수", "함수", "배열")는 허용, 무의미한 것만 차단
                meaningful_short = _re.search(r'[가-힣]{2,}|[a-zA-Z]{3,}', cleaned_text)
                if not meaningful_short:
                    stt_logger.debug(f"⚠️ Too Short Filtered: '{cleaned_text}'")
                    return Response({'status': 'silence_skipped', 'text': '', 'reason': f'Too short: {cleaned_text}'}, status=status.HTTP_200_OK)

            # [NEW] 2.6. 반복 음절 패턴 감지 (예: "아아아아", "음음음", "어어어어")
            if _re.match(r'^(.{1,3})\1{2,}$', cleaned_text.replace(' ', '')):
                stt_logger.debug(f"⚠️ Repeated Syllable Filtered: '{cleaned_text}'")
                return Response({'status': 'silence_skipped', 'text': '', 'reason': f'Repeated syllable: {cleaned_text}'}, status=status.HTTP_200_OK)

            # [FIX] 한글 비율 검사 — 영어 강의도 허용
            # 한글도 영어도 아닌 무작위 문자만 있는 경우만 차단
            korean_chars = len(_re.findall(r'[가-힣]', cleaned_text))
            english_chars = len(_re.findall(r'[a-zA-Z]', cleaned_text))
            total_alpha = korean_chars + english_chars
            if total_alpha > 10 and (korean_chars + english_chars) / max(len(cleaned_text.replace(' ', '')), 1) < 0.2:
                # 한글도 영어도 거의 없는 경우 (특수문자/기호만)
                has_code_pattern = _re.search(r'[{}()\[\];=<>]', cleaned_text)
                if not has_code_pattern:
                    is_hallucination = True
                    skip_reason = f'Low alpha ratio ({total_alpha}/{len(cleaned_text)})'

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
                stt_logger.debug(f"⚠️ Filtered: '{cleaned_text}' | Reason: {skip_reason}")
                print(f"⚠️ Filtered: '{cleaned_text}' | Reason: {skip_reason}")
                return Response({'status': 'silence_skipped', 'text': '', 'reason': skip_reason}, status=status.HTTP_200_OK)

            # [NEW] 5. 한국어 미완성 문장 캐시 (Sentence Buffering)
            from django.core.cache import cache
            cache_key = f"stt_buffer_{session.id}"
            buffered_text = cache.get(cache_key, "")

            # 한국어 종결 판단 함수
            def _is_sentence_complete(text):
                text = text.strip()
                if not text:
                    return False
                # 마침 부호
                if text[-1] in '.!?。':
                    return True
                # 한국어 종결어미 패턴
                endings = ['다', '요', '죠', '니다', '니까', '세요', '해요', '이요',
                           '까요', '네요', '군요', '잖아요', '거든요', '립니다',
                           '됩니다', '합니다', '입니다', '겠습니다', '습니다',
                           '어요', '아요', '었어요', '었다', '했다', '했어요',
                           '네', '지', '래', '야', '마', '거야', '거예요']
                for end in endings:
                    if text.endswith(end):
                        return True
                # 영어 문장은 항상 완성으로 간주 (영어 비율이 높을 때)
                eng_ratio = len(_re.findall(r'[a-zA-Z]', text)) / max(len(text.replace(' ', '')), 1)
                if eng_ratio > 0.5:
                    return True
                return False

            # 이전 버퍼와 합치기
            if buffered_text:
                cleaned_text = buffered_text + " " + cleaned_text
                stt_text = cleaned_text

            # 문장 완성 여부 확인
            if not _is_sentence_complete(cleaned_text):
                # 미완성 → 캐시에 보관, 응답은 빈 텍스트
                cache.set(cache_key, cleaned_text, timeout=120)  # 2분 TTL
                stt_logger.debug(f"📦 Buffered (incomplete): '{cleaned_text}'")
                return Response({'status': 'buffered', 'text': '', 'reason': 'Sentence incomplete, buffering'}, status=status.HTTP_200_OK)
            else:
                # 완성 → 캐시 클리어
                cache.delete(cache_key)

            # 6. video_offset 처리 (프론트엔드에서 전송)
            video_offset = request.data.get('video_offset')
            if video_offset:
                try:
                    video_offset = float(video_offset)
                except (ValueError, TypeError):
                    video_offset = None

            # 7. Save STT Log
            log = STTLog.objects.create(
                session=session,
                sequence_order=sequence_order,
                text_chunk=stt_text,
                video_offset=video_offset,
            )
            
            return Response({
                'status': 'processed', 
                'text': stt_text, 
                'id': log.id,
                'video_offset': video_offset,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            stt_logger.error(f"CRITICAL STT Error: {str(e)}")
            print(f"❌ CRITICAL STT Error: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='flush-buffer')
    def flush_stt_buffer(self, request, pk=None):
        """POST /api/learning/sessions/{id}/flush-buffer/
        녹음 종료 시 캐시에 남은 미완성 문장을 강제 저장
        """
        session = self.get_object()
        from django.core.cache import cache
        cache_key = f"stt_buffer_{session.id}"
        buffered_text = cache.get(cache_key, "")

        if not buffered_text or not buffered_text.strip():
            return Response({'status': 'empty', 'text': ''})

        # 버퍼 내용을 DB에 저장
        last_log = STTLog.objects.filter(session=session).order_by('-sequence_order').first()
        next_seq = (last_log.sequence_order + 1) if last_log else 1

        log = STTLog.objects.create(
            session=session,
            sequence_order=next_seq,
            text_chunk=buffered_text.strip(),
        )
        cache.delete(cache_key)

        return Response({
            'status': 'flushed',
            'text': buffered_text.strip(),
            'id': log.id,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='debug-openai')
    def debug_openai(self, request):
        # [SECURITY] DEBUG=True에서만 동작
        if not settings.DEBUG:
            return Response({"error": "Debug endpoint is disabled in production"}, status=status.HTTP_403_FORBIDDEN)
        from openai import OpenAI
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

    @action(detail=True, methods=['patch'], url_path='summary')
    def update_summary(self, request, pk=None):
        """PATCH /api/learning/sessions/{id}/summary/ — 학습노트 수정"""
        session = self.get_object()
        content_text = request.data.get('content_text', '').strip()
        if not content_text:
            return Response({'error': 'content_text는 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        summary = SessionSummary.objects.filter(session=session).order_by('-created_at').first()
        if summary:
            summary.content_text = content_text
            summary.save()
        else:
            summary = SessionSummary.objects.create(
                session=session,
                content_text=content_text,
                raw_stt_link="User Edited"
            )
        return Response({'id': summary.id, 'content_text': summary.content_text, 'message': '학습노트가 수정되었습니다.'})

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

        # 2. AI 요약 요청 (Real OpenAI Call + RAG)
        print("DEBUG: Calling OpenAI with RAG context...")
        summary_text = self._call_openai_summary(full_text, lecture_id=session.lecture_id)
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

    @action(detail=True, methods=['post'], url_path='classify-speakers')
    def classify_speakers(self, request, pk=None):
        """
        [후처리] 세션의 전체 STT 로그를 분석하여 화자(교수자/학생)를 일괄 분류
        전체 대화 맥락을 보고 판단하므로 실시간보다 정확함
        """
        session = self.get_object()
        logs = STTLog.objects.filter(session=session).order_by('sequence_order')
        
        if not logs.exists():
            return Response({'error': 'STT 로그가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 번호 매긴 텍스트 목록 구성
        numbered_lines = []
        log_ids = []
        for log in logs:
            numbered_lines.append(f"[{log.sequence_order}] {log.text_chunk}")
            log_ids.append((log.id, log.sequence_order))
        
        transcript_text = "\n".join(numbered_lines)
        
        # GPT-4o에게 전체 맥락으로 화자 분류 요청
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            result = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """너는 IT 강의 자막에서 화자를 구분하는 전문 분류기야.

아래 번호가 매겨진 자막을 읽고, 각 줄이 교수자(INSTRUCTOR)의 발화인지 학생(STUDENT)의 발화인지 판단해.

판단 기준:
- 설명, 강의, 코드 설명, 개념 전달 → INSTRUCTOR
- 질문, 짧은 응답("네", "아~"), 감탄, 되묻기 → STUDENT
- 판단이 어려우면 INSTRUCTOR로 분류 (강의에서 교수자 발화 비율이 높으므로)

반드시 아래 JSON 배열 형식으로만 출력해. 다른 텍스트는 절대 포함하지 마.
[{"seq": 1, "speaker": "INSTRUCTOR"}, {"seq": 2, "speaker": "STUDENT"}, ...]"""},
                    {"role": "user", "content": transcript_text}
                ],
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            
            import json
            raw_response = result.choices[0].message.content
            parsed = json.loads(raw_response)
            
            # 응답이 {"results": [...]} 또는 [...] 형태일 수 있음
            classifications = parsed if isinstance(parsed, list) else parsed.get('results', parsed.get('data', []))
            
            if not isinstance(classifications, list):
                # dict의 첫 번째 list 값을 찾음
                for v in parsed.values():
                    if isinstance(v, list):
                        classifications = v
                        break
            
            # DB 업데이트
            updated = 0
            seq_map = {item.get('seq'): item.get('speaker', 'UNKNOWN') for item in classifications if isinstance(item, dict)}
            
            for log_id, seq in log_ids:
                speaker = seq_map.get(seq, 'UNKNOWN')
                if speaker not in ('INSTRUCTOR', 'STUDENT'):
                    speaker = 'UNKNOWN'
                STTLog.objects.filter(id=log_id).update(speaker=speaker)
                updated += 1
            
            # 업데이트된 로그 반환
            updated_logs = STTLog.objects.filter(session=session).order_by('sequence_order')
            serializer = STTLogSerializer(updated_logs, many=True)
            
            return Response({
                'status': 'classified',
                'updated': updated,
                'logs': serializer.data,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Speaker classification error: {e}")
            return Response({'error': f'분류 실패: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        # DailyQuiz already imported at top
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

        # [New] 출석률 계산
        # 사용자가 등록한 강의들의 전체 수업일 대비 출석 비율
        # Lecture already imported at top
        enrolled_lectures = Lecture.objects.filter(students=user)
        total_class_dates = 0
        attended_dates_count = 0
        
        for lec in enrolled_lectures:
            # 이 강의에서 수업이 진행된 모든 날짜
            all_dates = (
                LearningSession.objects
                .filter(lecture=lec)
                .values_list('session_date', flat=True)
                .distinct()
            )
            dates_set = set(all_dates)
            total_class_dates += len(dates_set)
            
            # 이 학생이 출석한 날짜
            my_dates = (
                LearningSession.objects
                .filter(lecture=lec, student=user)
                .values_list('session_date', flat=True)
                .distinct()
            )
            attended_dates_count += len(set(my_dates) & dates_set)
        
        attendance_rate = round((attended_dates_count / total_class_dates * 100), 1) if total_class_dates > 0 else 0

        # [New] 🔥 학습 스트릭 계산 (연속 학습일)
        from datetime import timedelta, date as date_cls
        all_session_dates = set(
            LearningSession.objects.filter(student=user)
            .values_list('session_date', flat=True)
        )
        streak = 0
        check_date = date_cls.today()
        # 오늘 아직 학습 안 했으면 어제부터 카운트
        if check_date not in all_session_dates:
            check_date -= timedelta(days=1)
        while check_date in all_session_dates:
            streak += 1
            check_date -= timedelta(days=1)

        return Response({
            "finishedSessions": finished_count,
            "totalHours": total_hours,
            "totalHoursInt": total_hours_int,
            "totalMinutesInt": total_minutes_int,
            "todayHours": today_hours, 
            "quizScore": quiz_score,
            "attendanceRate": attendance_rate,
            "attendedDays": attended_dates_count,
            "totalClassDays": total_class_dates,
            "lastSessionDate": last_session_date,
            "lastSessionId": last_session.id if last_session else None,
            "lastSessionUrl": last_session.youtube_url if last_session else None,
            "streak": streak,
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
        [FIX] 라이브 세션 연결 시 LiveSTTLog도 함께 반환
        """
        session = self.get_object()

        # 1. 개인 STT 로그 (일반 세션)
        personal_logs = STTLog.objects.filter(session=session).order_by('sequence_order')

        # 2. 라이브 세션 연결 감지 → LiveSTTLog 병합
        live_session = self._get_linked_live_session(session)
        if live_session and not personal_logs.exists():
            # 개인 로그가 비어있고 라이브 세션이 연결되어 있으면 → LiveSTTLog 반환
            live_logs = LiveSTTLog.objects.filter(
                live_session=live_session
            ).order_by('sequence_order')

            # STTLogSerializer 포맷에 맞게 변환
            live_data = []
            for log in live_logs:
                live_data.append({
                    'id': log.id,
                    'session': session.id,
                    'sequence_order': log.sequence_order,
                    'text_chunk': log.text_chunk,
                    'speaker': 'INSTRUCTOR',  # 라이브 STT는 교수자 마이크
                    'video_offset': None,
                    'created_at': log.created_at.isoformat(),
                })
            return Response(live_data, status=status.HTTP_200_OK)

        # 개인 로그가 있으면 그대로 반환
        serializer = STTLogSerializer(personal_logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='debug-sessions')
    def debug_sessions(self, request):
        # [SECURITY] DEBUG=True에서만 동작
        if not settings.DEBUG:
            return Response({"error": "Debug endpoint is disabled in production"}, status=status.HTTP_403_FORBIDDEN)
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
        # [SECURITY] DEBUG=True에서만 동작
        if not settings.DEBUG:
            return Response({"error": "Debug endpoint is disabled in production"}, status=status.HTTP_403_FORBIDDEN)
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

    def _call_openai_summary(self, text, lecture_id=None):
        from openai import OpenAI
        from django.conf import settings
        
        # [Optimization] Set timeout to avoid hanging (180s = 3min)
        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=180.0)
        
        try:
            # [RAG] 공식 문서에서 관련 컨텍스트 검색
            rag_context = ""
            try:
                from .rag import RAGService
                rag = RAGService()
                # STT 텍스트에서 핵심 키워드 추출 (앞 500자 사용)
                search_query = text[:300]
                related_docs = rag.search(query=search_query, top_k=3, lecture_id=lecture_id)
                if related_docs:
                    rag_context = "\n".join([f"- {doc.content[:300]}" for doc in related_docs])
                    print(f"✅ [RAG] 요약 생성에 공식 문서 {len(related_docs)}건 참조")
            except Exception as rag_err:
                print(f"⚠️ [RAG] 검색 실패 (요약은 STT만으로 진행): {rag_err}")

            # System prompt defined as a variable to avoid indentation issues
            system_prompt = (
                "너는 IT 부트캠프의 '수석 정리 노트 작성자'야.\n"
                "학생들이 수업 내용을 나중에 다시 보고 완벽하게 복습할 수 있도록, \n"
                "제공된 [STT 스크립트]와 [공식 문서 참조]를 바탕으로 **구조화된 학습 자료(Lecture Note)**를 만들어줘.\n\n"
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
                "3. **문맥 파악**: '잠시만요', '들리시나요', '네네' 같은 무의미한 추임새는 전부 삭제하고, 핵심 정보만 남길 것.\n"
                "4. **공식 문서 참조**: [공식 문서 참조]가 제공되면, 전문 용어의 정확한 정의와 올바른 코드 예시를 반영할 것."
            )

            # 사용자 프롬프트 구성 (RAG 컨텍스트 포함)
            user_content = f"다음 수업 내용을 학습 자료로 정리해줘:\n\n{text}"
            if rag_context:
                user_content += f"\n\n[공식 문서 참조 (정확한 정의 및 예시)]:\n{rag_context}"

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=2500
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
    # [FIX] 노트 기능 (학습노트와 완전 분리, session.user_note 사용)
    # ──────────────────────────────────────────
    @action(detail=True, methods=['get', 'post'], url_path='note')
    def note(self, request, pk=None):
        """
        GET: 세션의 사용자 메모를 조회
        POST: 세션에 사용자 메모를 저장 (학습노트 건드리지 않음)
        """
        session = self.get_object()

        if request.method == 'GET':
            return Response({
                'has_note': bool(session.user_note),
                'note': session.user_note or '',
            })

        # POST
        note_text = request.data.get('note', '')
        if not note_text:
            return Response({'error': '메모 내용이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        session.user_note = note_text
        session.save(update_fields=['user_note'])

        return Response({
            'status': 'saved',
            'note': session.user_note,
        })


# Note: ChecklistViewSet has been moved to checklist_views.py
# It is re-exported at the top of this file for backward compatibility.

