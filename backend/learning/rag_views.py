from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .rag import RAGService
from .models import VectorStore

class RAGViewSet(viewsets.ViewSet):
    """
    RAG (Retrieval-Augmented Generation) 관련 API
    - 인덱싱 (Indexing): 학습 데이터를 벡터 DB에 저장
    - 검색 (Retrieval): 질문과 유사한 학습 내용 검색
    """
    permission_classes = [AllowAny] # For testing convenience

    @action(detail=False, methods=['post'], url_path='index-session')
    def index_session(self, request):
        """
        특정 세션 ID를 받아 강제로 인덱싱 수행
        Body: { "session_id": 123 }
        """
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            rag_service = RAGService()
            count = rag_service.index_session(session_id)
            return Response({'status': 'success', 'indexed_count': count}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        질문 검색
        Query Param: ?q=질문내용&lecture_id=XX
        """
        query = request.query_params.get('q')
        lecture_id = request.query_params.get('lecture_id')
        
        if not query:
            return Response({'error': 'Query parameter q is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            rag_service = RAGService()
            results = rag_service.search(query, top_k=5, lecture_id=lecture_id)
            
            data = []
            for res in results:
                data.append({
                    "content": res.content,
                    "distance": res.distance, # Lower is better
                    "source": res.source_type,
                    "created_at": res.created_at,
                    "session_id": res.session_id
                })
                
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
