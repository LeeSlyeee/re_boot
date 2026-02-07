from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Portfolio
from .serializers import PortfolioSerializer
from learning.models import SessionSummary, DailyQuiz
import openai
from django.conf import settings
from django.utils import timezone

openai.api_key = settings.OPENAI_API_KEY

class PortfolioViewSet(viewsets.ModelViewSet):
    """
    포트폴리오 관리 및 AI 생성 (취업용/창업용)
    """
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(student=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """
        AI를 이용해 포트폴리오/MVP기획을 자동 생성
        """
        user = request.user
        p_type = request.data.get('type', 'JOB') # JOB or STARTUP
        
        # 1. 학습 데이터 수집
        summaries = SessionSummary.objects.filter(session__student=user)
        all_text = "\n\n".join([f"[{s.created_at.date()}] {s.content_text}" for s in summaries])
        
        if not all_text:
            all_text = "아직 학습 기록이 충분하지 않습니다. 열심히 공부했음."

        # 2. 퀴즈 성취도 (평균 점수)
        quizzes = DailyQuiz.objects.filter(student=user)
        avg_score = 0
        if quizzes.exists():
            avg_score = sum([q.total_score for q in quizzes]) / quizzes.count()
            
        # 3. 프롬프트 구성
        if p_type == 'JOB':
            system_prompt = "당신은 IT 전문 커리어 컨설턴트입니다. 학생의 학습 기록을 바탕으로 구직용 포트폴리오를 작성해주세요."
            user_prompt = f"""
            학생의 다음 학습 요약과 성취도를 바탕으로, Markdown 형식의 포트폴리오를 작성해주세요.
            
            [학습 기록]
            {all_text[:5000]} 
            
            [평균 퀴즈 점수]
            {avg_score}점
            
            [요청 사항]
            - 전문적인 어조 사용
            - '핵심 역량(Key Skills)', '학습 프로젝트 요약', '자기소개서 초안' 포함
            - 학습한 내용을 바탕으로 어떤 기술 스택을 다룰 수 있는지 명시
            """
            default_title = f"IT 개발자 취업 포트폴리오 ({timezone.now().strftime('%Y-%m-%d')})"
        else:
            system_prompt = "당신은 스타트업 액셀러레이터의 멘토입니다. 학생이 배운 기술을 활용하여 구현 가능한 MVP 기술 명세서를 작성해주세요."
            user_prompt = f"""
            학생이 학습한 다음 기술들을 바탕으로, 실제 창업 시 구현 가능한 MVP(Minimum Viable Product) 기술 기획서를 작성해주세요.
            
            [학습 기록]
            {all_text[:5000]}
            
            [요청 사항]
            - 서비스 아이디어 제안 (배운 내용을 활용할 수 있는 서비스)
            - 필요한 기술 스택 (Frontend, Backend, DB 등)
            - 핵심 기능 명세
            - 4주 개발 로드맵
            """
            default_title = f"스타트업 MVP 기술 기획서 ({timezone.now().strftime('%Y-%m-%d')})"

        # 4. AI 호출
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            generated_content = response.choices[0].message['content']
            
            # 5. 저장
            portfolio = Portfolio.objects.create(
                student=user,
                portfolio_type=p_type,
                title=default_title,
                content=generated_content
            )
            
            return Response(PortfolioSerializer(portfolio).data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            # 에러 발생 시 로그 출력
            print(f"Portfolio Generation Error: {e}")
            return Response({'error': f"AI 생성 실패: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
