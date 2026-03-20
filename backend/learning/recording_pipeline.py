"""
강의 녹음 파일 → STT → 요약 가공 파이프라인
1시간 강의 기준 설계 (mp3 ~60MB, wav ~600MB → mp3 변환 후 처리)

파이프라인 흐름:
1. 오디오 파일 수신 + 임시 저장
2. pydub로 15분 단위 청크 분할 (Whisper 25MB 제한 대응)
3. 각 청크를 Whisper API로 STT 변환
4. 전체 텍스트 합산 → GPT-4o 요약
5. SessionSummary 저장 + RAG 인덱싱
"""

import os
import math
import tempfile
from pydub import AudioSegment
from openai import OpenAI
from django.conf import settings
from django.utils import timezone

from .models import (
    RecordingUpload, LearningSession, STTLog, SessionSummary
)


# ─── 설정 상수 ───
CHUNK_DURATION_MS = 15 * 60 * 1000   # 15분 단위 (1시간 → 4청크)
MAX_FILE_SIZE = 150 * 1024 * 1024     # 150MB (1시간 wav도 커버)
WHISPER_MAX_SIZE = 25 * 1024 * 1024   # Whisper API 제한 25MB
EXPORT_BITRATE = '64k'                # mp3 변환 시 비트율 (15분 ≒ 7MB)


def process_recording(recording_id: int) -> dict:
    """
    메인 파이프라인 실행 함수
    
    Args:
        recording_id: RecordingUpload의 PK
    
    Returns:
        dict: { "success": bool, "session_id": int|None, "summary": str|None, "error": str|None }
    """
    recording = RecordingUpload.objects.get(id=recording_id)
    
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # ── Step 1: 오디오 파일 로드 ──
        recording.status = 'SPLITTING'
        recording.save(update_fields=['status'])
        
        audio_path = recording.audio_file.path
        print(f"🎤 [Pipeline] 오디오 로드: {audio_path}")
        
        audio = AudioSegment.from_file(audio_path)
        duration_sec = len(audio) // 1000
        recording.duration_seconds = duration_sec
        
        total_chunks = math.ceil(len(audio) / CHUNK_DURATION_MS)
        recording.total_chunks = total_chunks
        recording.save(update_fields=['duration_seconds', 'total_chunks'])
        
        print(f"📊 [Pipeline] 총 길이: {duration_sec}초 ({duration_sec // 60}분), 청크 수: {total_chunks}")
        
        # ── Step 2: 청크 분할 + Whisper STT ──
        recording.status = 'TRANSCRIBING'
        recording.save(update_fields=['status'])
        
        # LearningSession 생성 (강사 계정으로)
        session = LearningSession.objects.create(
            student=recording.uploaded_by,
            lecture=recording.lecture,
            session_order=1,
            is_completed=True,
            end_time=timezone.now()
        )
        recording.session = session
        recording.save(update_fields=['session'])
        
        all_texts = []
        
        for i in range(total_chunks):
            start_ms = i * CHUNK_DURATION_MS
            end_ms = min((i + 1) * CHUNK_DURATION_MS, len(audio))
            chunk = audio[start_ms:end_ms]
            
            # 임시 mp3 파일로 변환 (Whisper는 mp3/wav/m4a 지원)
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                chunk.export(tmp.name, format='mp3', bitrate=EXPORT_BITRATE)
                chunk_path = tmp.name
            
            try:
                chunk_size = os.path.getsize(chunk_path)
                print(f"  📝 [Chunk {i+1}/{total_chunks}] "
                      f"{start_ms//1000//60}분~{end_ms//1000//60}분, "
                      f"크기: {chunk_size / 1024 / 1024:.1f}MB")
                
                # Whisper → gpt-4o-transcribe 업그레이드
                with open(chunk_path, 'rb') as audio_file:
                    # 이전 텍스트를 프롬프트로 전달 (정확도 향상)
                    previous_context = " ".join(all_texts[-2:])[-200:] if all_texts else ""
                    
                    transcript = client.audio.transcriptions.create(
                        model="gpt-4o-transcribe",
                        file=audio_file,
                        language="ko",
                        prompt=f"이것은 한국어 IT 부트캠프 강의 자막입니다. 이전 내용: {previous_context}" if previous_context else "이것은 한국어 IT 부트캠프 강의 자막입니다.",
                    )
                
                stt_text = transcript.text.strip()
                
                # 환각(hallucination) 필터링
                if _is_hallucination(stt_text):
                    print(f"  ⚠️ [Chunk {i+1}] 환각 감지 — 건너뜀")
                    stt_text = ""
                
                if stt_text:
                    all_texts.append(stt_text)
                    
                    # STTLog 저장
                    STTLog.objects.create(
                        session=session,
                        sequence_order=i + 1,
                        text_chunk=stt_text
                    )
                
            finally:
                # 임시 파일 정리
                if os.path.exists(chunk_path):
                    os.unlink(chunk_path)
            
            # 진행률 업데이트
            recording.processed_chunks = i + 1
            recording.progress = int(((i + 1) / total_chunks) * 80)  # STT = 80%
            recording.save(update_fields=['processed_chunks', 'progress'])
        
        # ── Step 3: AI 요약 생성 ──
        recording.status = 'SUMMARIZING'
        recording.progress = 85
        recording.save(update_fields=['status', 'progress'])
        
        full_text = "\n\n".join(all_texts)
        
        if not full_text.strip():
            recording.status = 'FAILED'
            recording.error_message = "STT 변환 결과가 비어있습니다. 오디오에 음성이 포함되어 있는지 확인해주세요."
            recording.save(update_fields=['status', 'error_message'])
            return {"success": False, "error": recording.error_message}
        
        print(f"📝 [Pipeline] 전체 STT 텍스트 길이: {len(full_text)}자")
        
        summary_text = _generate_summary(client, full_text, duration_sec)
        
        if summary_text:
            SessionSummary.objects.create(
                session=session,
                content_text=summary_text,
                raw_stt_link="녹음 파일 업로드 → 가공 파이프라인"
            )
            recording.progress = 95
            recording.save(update_fields=['progress'])
        
        # ── Step 4: RAG 인덱싱 ──
        try:
            from .rag import RAGService
            rag = RAGService()
            rag.index_session(session.id)
            print(f"✅ [Pipeline] RAG 인덱싱 완료 (Session {session.id})")
        except Exception as e:
            print(f"⚠️ [Pipeline] RAG 인덱싱 실패 (비치명적): {e}")
        
        # ── 완료 ──
        recording.status = 'COMPLETED'
        recording.progress = 100
        recording.completed_at = timezone.now()
        recording.save(update_fields=['status', 'progress', 'completed_at'])
        
        print(f"✅ [Pipeline] 파이프라인 완료! Session ID: {session.id}")
        
        return {
            "success": True,
            "session_id": session.id,
            "summary": summary_text,
            "duration_minutes": duration_sec // 60,
            "total_chunks": total_chunks,
            "stt_length": len(full_text),
        }
        
    except Exception as e:
        recording.status = 'FAILED'
        recording.error_message = str(e)
        recording.save(update_fields=['status', 'error_message'])
        print(f"❌ [Pipeline] 실패: {e}")
        return {"success": False, "error": str(e)}


def _is_hallucination(text: str) -> bool:
    """Whisper 환각(hallucination) 필터"""
    if not text or len(text) < 3:
        return True
    
    HALLUCINATIONS = [
        "시청해주셔서 감사합니다", "시청해 주셔서 감사합니다",
        "구독과 좋아요", "좋아요와 구독", "MBC 뉴스", "SBS 뉴스",
        "KBS 뉴스", "Thanks for watching", "Thank you for watching",
        "Subtitles by", "자막 제작", "오늘도 봐주셔서 감사합니다",
    ]
    
    for h in HALLUCINATIONS:
        if h in text:
            return True
    
    # 반복 문자 감지 (예: "뷔 뷔 뷔 뷔")
    words = text.split()
    if len(words) >= 3 and len(set(words)) <= 2:
        return True
    
    return False


def _generate_summary(client: OpenAI, full_text: str, duration_sec: int) -> str:
    """
    강의 전체 텍스트를 GPT-4o로 요약
    1시간 분량의 텍스트도 처리 가능하도록 설계
    """
    # 1시간 강의 ≒ 약 8,000~15,000 단어 (한국어) ≒ 약 20,000~40,000 토큰
    # GPT-4o의 128K 컨텍스트 윈도우 안에 충분히 들어감
    
    duration_min = duration_sec // 60
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 대학 강의를 전문적으로 요약하는 AI 어시스턴트입니다.\n"
                        "아래는 강의실 녹음을 STT로 전사한 텍스트입니다.\n"
                        "이를 학생들이 복습하기 좋은 형태로 체계적으로 요약해주세요.\n\n"
                        "형식:\n"
                        "# 📚 강의 요약\n\n"
                        "## 핵심 주제\n- 주요 주제 나열\n\n"
                        "## 상세 내용\n### 1. 세부 주제\n- 설명\n\n"
                        "## 핵심 키워드\n- 중요 용어와 짧은 설명\n\n"
                        "## 복습 포인트\n- 시험에 나올 만한 핵심 사항"
                    )
                },
                {
                    "role": "user",
                    "content": f"[강의 시간: 약 {duration_min}분]\n\n{full_text}"
                }
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"❌ [Summary] GPT-4o 요약 실패: {e}")
        
        # Fallback: 간단 요약
        lines = full_text.split('\n')
        fallback = f"# 📚 강의 요약 (자동 생성 실패 — 원문 일부)\n\n"
        fallback += f"**강의 시간**: 약 {duration_min}분\n\n"
        fallback += "## 강의 내용 (원문 앞부분)\n\n"
        fallback += full_text[:3000] + "\n\n..."
        return fallback
