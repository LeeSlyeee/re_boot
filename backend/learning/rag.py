import openai
from django.conf import settings
from .models import VectorStore, LearningSession, SessionSummary, STTLog, Lecture
from pgvector.django import L2Distance, CosineDistance

class RAGService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=self.api_key)

    def get_embedding(self, text):
        text = text.replace("\n", " ")
        response = self.client.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    def index_session(self, session_id):
        """
        특정 세션의 학습 데이터(요약본, STT)를 벡터 DB에 인덱싱합니다.
        기존 데이터가 있다면 삭제 후 재생성합니다.
        """
        session = LearningSession.objects.get(id=session_id)
        
        # 1. 기존 벡터 삭제 (중복 방지)
        VectorStore.objects.filter(session=session).delete()
        
        indexed_count = 0

        # 2. 요약본(SessionSummary) 인덱싱
        summaries = SessionSummary.objects.filter(session=session)
        for summary in summaries:
            if not summary.content_text:
                continue
            
            # 요약본이 너무 길면 쪼갤 수도 있지만, 일단 전체를 하나로 (또는 문단별로)
            # 여기서는 문단 단위로 쪼개서 저장
            paragraphs = summary.content_text.split('\n\n')
            for p in paragraphs:
                if len(p.strip()) < 10: continue
                
                embedding = self.get_embedding(p)
                VectorStore.objects.create(
                    content=p,
                    embedding=embedding,
                    session=session,
                    lecture=session.lecture,
                    source_type='summary'
                )
                indexed_count += 1
        
        print(f"Index complete for Session {session_id}: {indexed_count} vectors created.")
        return indexed_count

    def search(self, query, top_k=3, lecture_id=None):
        """
        질문(Query)과 가장 유사한 학습 내용을 검색합니다.
        """
        query_embedding = self.get_embedding(query)
        
        # Cosine Distance (1 - Cosine Similarity)가 작을수록 유사함
        # pgvector에서는 CosineDistance 사용 시 오름차순 정렬하면 됨
        
        qs = VectorStore.objects.annotate(
            distance=CosineDistance('embedding', query_embedding)
        ).order_by('distance')

        if lecture_id:
            qs = qs.filter(lecture_id=lecture_id)
            
        return qs[:top_k]

    def generate_answer(self, query, session_id=None, lecture_id=None):
        """
        [고도화된 RAG 답변 생성]
        1. Context Search: 질문과 관련된 학습 내용 검색
        2. Session Context: 현재 대화의 압축된 문맥 조회
        3. Generative Answer: LLM을 통해 답변 생성
        """
        # 1. 관련 지식 검색 (Retrieval)
        related_docs = self.search(query, top_k=3, lecture_id=lecture_id)
        knowledge_context = "\n".join([f"- {doc.content}" for doc in related_docs])
        
        # 2. 대화 문맥 조회 (Conversation Context)
        conversation_context = ""
        if session_id:
            from .context import ContextManager
            cm = ContextManager()
            conversation_context = cm.get_full_context(session_id)
            
        # 3. 프롬프트 구성 (Augmented Generation)
        system_prompt = """
        너는 IT 부트캠프의 친절한 'AI 튜터'야.
        학생의 질문에 대해 [관련 학습 내용]과 [대화 문맥]을 바탕으로 명확하게 답변해줘.
        
        [답변 규칙]
        1. 질문과 가장 관련 있는 학습 내용을 우선적으로 설명할 것.
        2. 이전에 나눈 대화 맥락(Context)을 고려하여 답변할 것. (예: "아까 말씀하신대로...")
        3. 내용은 초보자도 이해하기 쉽게 설명할 것.
        4. 정보가 부족하면 솔직하게 모른다고 할 것.
        """
        
        user_prompt = f"""
        [관련 학습 내용 (Knowledge)]:
        {knowledge_context}
        
        [대화 문맥 (Current Context)]:
        {conversation_context}
        
        [학생의 질문]:
        {query}
        
        [답변]:
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"죄송합니다. 답변 생성 중 오류가 발생했습니다. ({str(e)})"
