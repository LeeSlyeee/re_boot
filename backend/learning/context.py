from django.conf import settings
from .models import LearningSession, STTLog
import openai
from django.utils import timezone
from datetime import timedelta

class ContextManager:
    """
    [대화 압축 및 화자 분리 컨텍스트 관리자]
    - Long Context를 압축(Summarize)하여 토큰 비용 절감
    - 다화자(Multi-Speaker) 환경에서 화자 식별
    """
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.compression_threshold = 10  # 대화 10턴마다 압축 시도 (테스트용)
        # self.compression_threshold = 50 # 실전용 권장값

    def compress_session_if_needed(self, session_id):
        """
        특정 세션의 로그를 확인하고, 압축 시점이 도래했으면 압축 수행
        """
        session = LearningSession.objects.get(id=session_id)
        
        # 1. 최근 압축 이후 쌓인 새 로그 조회 (last_compressed_at 기준이 아니라, 이미 처리된 시점을 별도 기록하거나 로그 수로 판단)
        # 여기서는 간단히: 전체 로그 수 확인
        total_logs = STTLog.objects.filter(session=session).count()
        
        # (임시 로직) 그냥 항상 압축하는 건 비효율적이므로, 
        # 실제로는 '마지막 압축된 sequence_order'를 저장하는 필드가 필요함.
        # 하지만 지금은 모델 변경 최소화를 위해 '시간'으로 체크하거나 '로그 개수'로 체크
        
        # 예: 10개 단위로 끊어서 압축
        # if total_logs % self.compression_threshold != 0:
        #     return False

        # [Better Logic] 
        # 현재 context_summary가 비어있으면 -> 첫 압축
        # 이미 있으면 -> Incremental Update
        
        # 최근 10분 내에 압축했으면 생략 (너무 잦은 압축 방지)
        if session.last_compressed_at and (timezone.now() - session.last_compressed_at) < timedelta(minutes=5):
             return False

        # 압축 실행
        self._perform_compression(session)
        return True

    def _perform_compression(self, session):
        # 1. 전체 또는 최근 로그 가져오기
        logs = STTLog.objects.filter(session=session).order_by('sequence_order')
        full_text = " ".join([f"[{log.created_at.strftime('%H:%M')}] {log.text_chunk}" for log in logs])
        
        if not full_text.strip():
            return

        # 2. OpenAI에게 '누적 요약' 요청
        print(f"DEBUG: Compressing Session {session.id} (Length: {len(full_text)})")
        
        current_summary = session.context_summary or "없음"
        
        prompt = f"""
        너는 대화 기록 관리자야. 
        아래 제공된 '이전 요약'과 '새로운 대화 내용'을 합쳐서, 
        **최신 상태의 단일 압축 요약본(Context Summary)**을 갱신해줘.
        
        [규칙]
        1. 핵심 주제, 결정된 사항, 사용자의 주요 질문을 위주로 요약할 것.
        2. 불필요한 인사말이나 반복은 제거할 것.
        3. 3~5문장 내외로 간결하게 작성할 것.
        4. (필수) 화자가 여러 명일 경우, 식별 가능한 정보(학생 A, 강사 등)가 있다면 명시할 것.
        
        [이전 요약]:
        {current_summary}
        
        [새로운 대화 내용]:
        {full_text}
        
        [갱신된 요약]:
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "You are a helpful assistant for summarizing conversation context."},
                          {"role": "user", "content": prompt}],
                max_tokens=500
            )
            
            new_summary = response.choices[0].message.content
            
            # 3. DB 업데이트
            session.context_summary = new_summary
            session.last_compressed_at = timezone.now()
            session.save()
            print(f"DEBUG: Compression Complete. Summary: {new_summary[:50]}...")
            
        except Exception as e:
            print(f"Compression Error: {e}")

    def get_full_context(self, session_id):
        """
        RAG나 챗봇이 사용할 '완성된 프롬프트 컨텍스트' 반환
        Format: [압축된 과거 기억] + [최근 대화 원본]
        """
        session = LearningSession.objects.get(id=session_id)
        
        # 1. 압축된 과거
        context = f"[--- 지난 대화 요약 ---]\n{session.context_summary or '(없음)'}\n\n"
        
        # 2. 최근 대화 (아직 압축 안 된, 혹은 최근 N개)
        # 여기서는 단순히 최근 5개만 원본으로 붙여줌 (Short-term memory)
        recent_logs = STTLog.objects.filter(session=session).order_by('-sequence_order')[:5]
        recent_logs = reversed(recent_logs) # 시간순 정렬
        
        context += "[--- 최근 대화 ---]\n"
        for log in recent_logs:
            context += f"- {log.text_chunk}\n"
            
        return context
