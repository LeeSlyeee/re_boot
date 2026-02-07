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
