from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .rag import RAGService
from .models import VectorStore, LiveQuestion, LiveParticipant, LiveSession

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
                    "distance": res.distance,
                    "source": res.source_type,
                    "created_at": res.created_at,
                    "session_id": res.session_id
                })
                
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='ask')
    def ask(self, request):
        """
        [고도화된 RAG 질문]
        Body: { "q": "질문", "session_id": 123 (선택), "lecture_id": 4 (선택), "live_session_id": 5 (선택) }
        
        live_session_id가 있으면 → AI 답변 + 교수자 대시보드에 익명 자동 전달
        """
        query = request.data.get('q')
        session_id = request.data.get('session_id')
        lecture_id = request.data.get('lecture_id')
        live_session_id = request.data.get('live_session_id')
        
        if not query:
             return Response({'error': 'Query is required'}, status=status.HTTP_400_BAD_REQUEST)

        rag_service = RAGService()
        answer = rag_service.generate_answer(query, session_id=session_id, lecture_id=lecture_id)
        
        # 라이브 세션 중이면 → 자동으로 LiveQuestion에 저장 (교수자에게 익명 전달)
        live_question_id = None
        if live_session_id and request.user.is_authenticated:
            try:
                live_session = LiveSession.objects.get(id=live_session_id, status='LIVE')
                if live_session.participants.filter(student=request.user).exists():
                    lq = LiveQuestion.objects.create(
                        live_session=live_session,
                        student=request.user,
                        question_text=query,
                        ai_answer=answer,
                    )
                    live_question_id = lq.id
            except LiveSession.DoesNotExist:
                pass  # 라이브 세션이 없거나 종료됨 → 무시, 기존 동작 유지
        
        return Response({
            'answer': answer,
            'live_question_id': live_question_id,
        }, status=status.HTTP_200_OK)
