from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Portfolio, MockInterview, InterviewExchange
from .serializers import MockInterviewSerializer
from django.conf import settings
from django.shortcuts import get_object_or_404
from openai import OpenAI

class InterviewViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MockInterviewSerializer
    
    def get_queryset(self):
        return MockInterview.objects.filter(student=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='start')
    def start_interview(self, request):
        """
        [Start Mock Interview]
        1. Create Interview Session
        2. Generate First Question based on Portfolio & Persona
        """
        user = request.user
        portfolio_id = request.data.get('portfolio_id')
        persona = request.data.get('persona', 'TECH_LEAD')
        
        portfolio = get_object_or_404(Portfolio, id=portfolio_id)
        
        # 1. Create Session
        interview = MockInterview.objects.create(
            student=user,
            portfolio=portfolio,
            persona=persona,
            status='IN_PROGRESS'
        )
        
        # 2. Get Skill Blocks (Re-use logic or fetch again)
        # For simplicity, we assume portfolio content has context, or we can fetch skills again.
        # Let's fetch skills for better context.
        from learning.models import StudentChecklist
        skills_qs = StudentChecklist.objects.filter(
            student=user, is_checked=True
        ).select_related('objective')
        skill_texts = [s.objective.content for s in skills_qs]
        skills_context = ", ".join(skill_texts) if skill_texts else "없음"

        # 3. Generate First Question
        system_prompt = self._get_system_prompt(persona)
        user_prompt = f"""
        [Portfolio]: {portfolio.content[:2000]}...
        [Skills]: {skills_context}
        
        위 내용을 바탕으로 면접을 시작합니다. 첫 번째 질문을 던지세요.
        인사말 없이 바로 핵심 질문을 하세요.
        """
        
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            first_question = response.choices[0].message.content
            
            # Save Question
            InterviewExchange.objects.create(
                interview=interview,
                question=first_question,
                order=1
            )
            
            return Response({
                "interview_id": interview.id,
                "persona": interview.get_persona_display(),
                "question": first_question
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"OpenAI Error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='chat')
    def chat_interview(self, request, pk=None):
        """
        [Interact]
        1. Receive User Answer
        2. Analyze & Score Answer (Multi-dimensional Rubric)
        3. Generate Follow-up Question
        """
        interview = self.get_object()
        answer_text = request.data.get('answer')
        
        # Get Current Question (Last one)
        current_exchange = interview.exchanges.last()
        
        if not current_exchange:
             return Response({"error": "No active question found"}, status=status.HTTP_400_BAD_REQUEST)

        # Update Answer
        current_exchange.answer = answer_text
        current_exchange.save()
        
        # AI Interaction
        system_prompt = self._get_system_prompt(interview.persona)
        
        # Construct Context (History)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add History (Last 3 exchanges)
        history = interview.exchanges.order_by('order')
        for ex in history:
            messages.append({"role": "assistant", "content": ex.question})
            if ex.answer:
                 messages.append({"role": "user", "content": ex.answer})
        
        # Prompt for Multi-dimensional Rubric Feedback & Next Question
        next_prompt = """
        사용자의 답변을 아래 4가지 차원으로 평가하세요.
        각 차원은 0~100점으로 채점하고, 구체적인 근거를 1줄 코멘트로 제시하세요.
        
        [평가 차원 (Rubric)]
        1. technical_depth (기술적 깊이): 개념의 정확성, 기술 선택의 이유, 대안 기술 비교
        2. logical_coherence (논리적 일관성): 답변 구조, STAR(상황-과제-행동-결과) 기법 준수, 인과관계의 명확성
        3. communication (소통 능력): 설명의 명확성, 적절한 예시 활용, 질문 의도 파악
        4. problem_solving (문제 해결력): 실무 적용 능력, 예외/엣지 케이스 고려, 창의적 접근
        
        그리고 종합 피드백과 다음 질문을 생성하세요.
        
        응답 형식 (JSON):
        {
            "rubric": {
                "technical_depth": {"score": 85, "comment": "개념은 정확하나 대안 기술 비교가 부족"},
                "logical_coherence": {"score": 70, "comment": "STAR 구조 중 Result 부분이 약함"},
                "communication": {"score": 90, "comment": "예시가 구체적이고 설명이 명확"},
                "problem_solving": {"score": 60, "comment": "엣지 케이스 고려가 부족"}
            },
            "overall_score": 76,
            "feedback": "종합 피드백 (2-3줄)",
            "next_question": "다음 질문"
        }
        """
        messages.append({"role": "system", "content": next_prompt})

        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"}
            )
            import json
            result = json.loads(response.choices[0].message.content)
            
            # Rubric 데이터를 feedback에 JSON으로 저장
            rubric = result.get('rubric', {})
            overall_score = result.get('overall_score', 0)
            feedback_text = result.get('feedback', '')
            
            # feedback 필드에 구조화된 데이터 저장 (JSON 형태)
            structured_feedback = json.dumps({
                'rubric': rubric,
                'feedback': feedback_text
            }, ensure_ascii=False)
            
            current_exchange.feedback = structured_feedback
            current_exchange.score = overall_score
            current_exchange.save()
            
            # Create Next Question
            next_q = result.get('next_question')
            if next_q:
                InterviewExchange.objects.create(
                    interview=interview,
                    question=next_q,
                    order=current_exchange.order + 1
                )
            
            return Response({
                "rubric": rubric,
                "overall_score": overall_score,
                "feedback": feedback_text,
                "next_question": next_q
            })

        except Exception as e:
            print(f"OpenAI Error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='finish')
    def finish_interview(self, request, pk=None):
        """
        [면접 종료 및 결과 리포트 생성]
        - 모든 교환의 Rubric 점수를 집계
        - 차원별 평균 점수 + 종합 분석 리포트 생성
        """
        import json
        interview = self.get_object()
        interview.status = 'COMPLETED'
        interview.save()
        
        exchanges = interview.exchanges.filter(score__gt=0).order_by('order')
        
        if not exchanges.exists():
            return Response({
                'status': 'completed',
                'message': '채점된 답변이 없습니다.',
                'report': None
            })
        
        # Rubric 차원별 점수 집계
        dimensions = {
            'technical_depth': {'scores': [], 'label': '기술적 깊이'},
            'logical_coherence': {'scores': [], 'label': '논리적 일관성'},
            'communication': {'scores': [], 'label': '소통 능력'},
            'problem_solving': {'scores': [], 'label': '문제 해결력'}
        }
        
        overall_scores = []
        best_exchange = None
        worst_exchange = None
        
        for ex in exchanges:
            overall_scores.append(ex.score)
            
            # Best/Worst 판별
            if best_exchange is None or ex.score > best_exchange.score:
                best_exchange = ex
            if worst_exchange is None or ex.score < worst_exchange.score:
                worst_exchange = ex
            
            # Rubric 파싱
            try:
                feedback_data = json.loads(ex.feedback)
                rubric = feedback_data.get('rubric', {})
                for dim_key in dimensions:
                    if dim_key in rubric:
                        dimensions[dim_key]['scores'].append(rubric[dim_key].get('score', 0))
            except (json.JSONDecodeError, TypeError):
                # 이전 형식(단순 텍스트) 호환
                pass
        
        # 차원별 평균 계산
        dimension_averages = {}
        for dim_key, dim_data in dimensions.items():
            scores = dim_data['scores']
            avg = round(sum(scores) / len(scores), 1) if scores else 0
            dimension_averages[dim_key] = {
                'label': dim_data['label'],
                'average': avg,
                'count': len(scores)
            }
        
        overall_avg = round(sum(overall_scores) / len(overall_scores), 1) if overall_scores else 0
        
        report = {
            'interview_id': interview.id,
            'persona': interview.get_persona_display(),
            'total_questions': exchanges.count(),
            'overall_average': overall_avg,
            'dimensions': dimension_averages,
            'best_answer': {
                'question': best_exchange.question[:100] if best_exchange else '',
                'score': best_exchange.score if best_exchange else 0
            },
            'needs_improvement': {
                'question': worst_exchange.question[:100] if worst_exchange else '',
                'score': worst_exchange.score if worst_exchange else 0
            },
            'disclaimer': '⚠️ 본 평가는 AI가 자동 생성한 참고 자료이며, 전문가 검증을 거치지 않았습니다. STAR 기법 및 업계 통용 면접 평가 프레임워크를 참고하였으나, 실제 채용 면접의 공식 평가로 사용될 수 없습니다.'
        }
        
        return Response({
            'status': 'completed',
            'report': report
        })

    def _get_system_prompt(self, persona):
        prompts = {
            'TECH_LEAD': "당신은 10년차 시니어 개발자입니다. 지원자의 기술적 깊이를 집요하게 파고드세요. 'Why'에 집중하고, 대안 기술과의 비교를 요구하세요.",
            'FRIENDLY_SENIOR': "당신은 지원자의 멘토가 될 수 있는 사람을 찾습니다. 편안한 분위기를 유도하되, 성장 가능성과 팀 적응력을 확인하는 질문을 하세요.",
            'HR_MANAGER': "당신은 채용 담당자입니다. 기술보다는 지원자의 성격, 가치관, 갈등 해결 경험 등 소프트 스킬에 집중하세요.",
            'STARTUP_CEO': "당신은 초기 스타트업 창업자입니다. 기술적 완성도보다 '속도', '비즈니스 가치', '주도적인 문제 해결' 경험을 물어보세요.",
            'BIG_TECH': "당신은 구글/메타 스타일의 면접관입니다. CS 기초(자료구조/알고리즘) 원리와 대규모 트래픽 처리에 대한 이해도를 검증하세요.",
            'PRESSURE': "당신은 지원자의 멘탈을 테스트하는 면접관입니다. 답변의 허점을 날카롭게 지적하고, 곤란한 상황을 가정하여 어떻게 대처하는지 확인하세요."
        }
        return prompts.get(persona, prompts['TECH_LEAD'])
