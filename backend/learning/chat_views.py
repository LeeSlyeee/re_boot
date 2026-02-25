"""
AI 튜터 챗봇 API Views
======================
RAG 기반 AI 튜터 — 35,000+ 공식 문서 벡터를 활용하여 학습 질문에 답변

Endpoints:
  POST /api/learning/chat/sessions/          → 새 채팅 세션 생성
  GET  /api/learning/chat/sessions/          → 내 채팅 세션 목록
  GET  /api/learning/chat/sessions/{id}/     → 세션 상세 (메시지 포함)
  POST /api/learning/chat/sessions/{id}/ask/ → 질문하기 (RAG 답변 생성)
  DELETE /api/learning/chat/sessions/{id}/   → 세션 삭제
"""
import re
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from .models import AIChatSession, AIChatMessage, VectorStore, Lecture
from .rag import RAGService
from .serializers import (
    AIChatSessionSerializer,
    AIChatSessionDetailSerializer,
    AIChatMessageSerializer,
)


class AIChatViewSet(viewsets.ModelViewSet):
    """AI 튜터 챗봇 ViewSet"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AIChatSessionSerializer

    def get_queryset(self):
        return AIChatSession.objects.filter(
            student=self.request.user
        ).prefetch_related('messages')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AIChatSessionDetailSerializer
        return AIChatSessionSerializer

    def perform_create(self, serializer):
        lecture_id = self.request.data.get('lecture_id')
        lecture = None
        if lecture_id:
            try:
                lecture = Lecture.objects.get(id=lecture_id)
            except Lecture.DoesNotExist:
                pass

        session = serializer.save(
            student=self.request.user,
            lecture=lecture,
        )

        # 시스템 메시지 추가
        lecture_name = lecture.title if lecture else "전체 기술 스택"
        AIChatMessage.objects.create(
            session=session,
            sender='SYSTEM',
            message=f"안녕하세요! 🎓 [{lecture_name}] 관련 질문에 답변해드리는 AI 튜터입니다.\n"
                    f"궁금한 점을 자유롭게 물어보세요. 20개+ 공식 문서를 기반으로 정확한 답변을 드립니다."
        )

    @action(detail=True, methods=['post'])
    def ask(self, request, pk=None):
        """질문하기 — RAG 기반 답변 생성"""
        session = self.get_object()
        question = request.data.get('message', '').strip()

        if not question:
            return Response(
                {'error': '질문을 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. 사용자 메시지 저장
        AIChatMessage.objects.create(
            session=session,
            sender='USER',
            message=question,
        )

        # 2. 세션 제목 자동 생성 (첫 질문에서)
        if not session.title:
            session.title = question[:50] + ('...' if len(question) > 50 else '')
            session.save(update_fields=['title'])

        # 3. RAG 검색 + 답변 생성
        try:
            rag = RAGService()

            # 관련 문서 검색 (material + session 모두 포함)
            related_docs = rag.search(
                query=question,
                top_k=5,
                lecture_id=session.lecture_id,
            )

            # 소스 정보 추출
            sources = []
            knowledge_context = ""
            for doc in related_docs:
                content_preview = doc.content[:200]
                # 출처 URL 추출
                url_match = re.search(r'출처:\s*(https?://\S+)', doc.content)
                source_url = url_match.group(1) if url_match else ''
                # 기술명 추출
                tech_match = re.search(r'기술:\s*(.+?)[\n(]', doc.content)
                tech_name = tech_match.group(1).strip() if tech_match else doc.source_type

                sources.append({
                    'title': tech_name,
                    'url': source_url,
                    'preview': content_preview[:100],
                })
                knowledge_context += f"\n- {doc.content}"

            # 대화 이력 구성 (최근 10개)
            recent_messages = AIChatMessage.objects.filter(
                session=session,
                sender__in=['USER', 'AI']
            ).order_by('-created_at')[:10]
            conversation_history = "\n".join([
                f"{'학생' if m.sender == 'USER' else 'AI'}: {m.message[:200]}"
                for m in reversed(list(recent_messages))
            ])

            # GPT 답변 생성
            answer = rag.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """너는 Re:Boot IT 부트캠프의 전문 AI 튜터야.
학생의 질문에 대해 [공식 문서 지식]과 [대화 맥락]을 바탕으로 **체계적이고 교육적으로** 답변해.

## 답변 형식 (반드시 마크다운으로 작성)

### 1️⃣ 핵심 개념 한 줄 요약
> 핵심 내용을 한 줄로 정리

### 2️⃣ 상세 설명
- 개념을 **초보자도 이해할 수 있도록** 비유와 함께 설명
- 관련된 하위 개념은 불릿 포인트로 정리
- **중요 키워드**는 볼드 처리

### 3️⃣ 코드 예시
```언어
// 실제 동작하는 코드 예시 포함
```
- 코드에 대한 라인별 설명 추가

### 4️⃣ 실전 팁 💡
- 실무에서 자주 쓰이는 패턴이나 주의사항

## 규칙
- 한국어로 답변, 기술 용어는 영어 병기 (예: 반응성(Reactivity))
- 정보가 부족하면 솔직히 말하고 공식 문서 URL 안내
- 이전 대화 맥락을 고려하여 자연스럽게 이어가기
- 답변은 항상 마크다운 형식으로 가독성 있게 작성"""},
                    {"role": "user", "content": f"""
[공식 문서 지식 (Knowledge)]:
{knowledge_context[:3000]}

[이전 대화]:
{conversation_history}

[학생의 질문]:
{question}

위 형식에 맞춰 친절하고 체계적으로 답변해줘.
                    """}
                ],
                max_tokens=3000,
            )
            ai_answer = answer.choices[0].message.content

        except Exception as e:
            ai_answer = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
            sources = []

        # 4. AI 답변 메시지 저장
        ai_msg = AIChatMessage.objects.create(
            session=session,
            sender='AI',
            message=ai_answer,
            sources=sources[:5],
        )

        # 세션 updated_at 갱신
        session.save(update_fields=['updated_at'])

        return Response({
            'answer': ai_answer,
            'sources': sources[:5],
            'message_id': ai_msg.id,
            'session_id': session.id,
        })
