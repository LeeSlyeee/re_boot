from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Portfolio, MockInterview, InterviewExchange
from .serializers import MockInterviewSerializer
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
        1. Create Interview Session with optional limits (max_questions or max_minutes)
        2. Generate First Question based on Portfolio & Persona
        """
        user = request.user
        portfolio_id = request.data.get('portfolio_id')
        persona = request.data.get('persona', 'TECH_LEAD')
        max_questions = request.data.get('max_questions')  # None = 무제한
        max_minutes = request.data.get('max_minutes')      # None = 무제한
        
        portfolio = get_object_or_404(Portfolio, id=portfolio_id)
        
        # 1. Create Session
        interview = MockInterview.objects.create(
            student=user,
            portfolio=portfolio,
            persona=persona,
            status='IN_PROGRESS',
            max_questions=max_questions,
            max_minutes=max_minutes
        )
        
        # 2. Get Skill Blocks for context
        from learning.models import StudentChecklist
        skills_qs = StudentChecklist.objects.filter(
            student=user, is_checked=True
        ).select_related('objective')
        skill_texts = [s.objective.content for s in skills_qs]
        skills_context = ", ".join(skill_texts) if skill_texts else "없음"

        # 3. Build limit context for AI
        limit_context = ""
        if max_questions:
            limit_context = f"\n이 면접은 총 {max_questions}개의 질문으로 진행됩니다. 각 질문의 중요도를 높여 핵심적인 부분을 물어보세요."
        elif max_minutes:
            limit_context = f"\n이 면접은 약 {max_minutes}분 동안 진행됩니다. 시간에 맞게 핵심적인 질문을 하세요."

        # 4. Generate First Question
        system_prompt = self._get_system_prompt(persona) + limit_context
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
                "question": first_question,
                "max_questions": interview.max_questions,
                "max_minutes": interview.max_minutes,
                "current_question": 1,
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
        3. Check if limit reached → if so, don't generate next question, signal auto_finish
        4. Generate Follow-up Question (if not finished)
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
        
        # Check limits
        answered_count = interview.exchanges.filter(answer__gt='').count()
        is_last_question = False
        
        if interview.max_questions and answered_count >= interview.max_questions:
            is_last_question = True
        
        if interview.max_minutes:
            elapsed = (timezone.now() - interview.created_at).total_seconds() / 60
            if elapsed >= interview.max_minutes:
                is_last_question = True
        
        # AI Interaction
        system_prompt = self._get_system_prompt(interview.persona)
        
        # Construct Context (History)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add History
        history = interview.exchanges.order_by('order')
        for ex in history:
            messages.append({"role": "assistant", "content": ex.question})
            if ex.answer:
                 messages.append({"role": "user", "content": ex.answer})
        
        # 공통 루브릭 (점수대별 구체 기준)
        scoring_rubric = """
[평가 차원 및 채점 기준 (Rubric)]

아래 4개 차원 각각을 0~100점으로 채점하되, 반드시 아래 점수대 기준에 따라 채점하세요.
"느낌"이 아니라 "근거"로 채점하세요.

━━━ 1. technical_depth (기술적 깊이) ━━━
평가 관점: 개념의 정확성, 기술 선택의 이유, 대안 기술과의 비교
- 90~100: 핵심 개념을 정확히 설명하고, "왜 이 기술을 선택했는지" 대안(2개 이상)과 비교하며 근거를 제시함
- 70~89:  핵심 개념이 정확하고, 기술 선택 이유를 1가지 이상 설명함. 대안 비교는 부분적
- 50~69:  개념을 대체로 알고 있으나, 부정확한 부분이 있거나 선택 이유가 불명확함
- 30~49:  개념 설명이 피상적이거나 오류가 있음. 기술 선택 이유를 말하지 못함
- 0~29:   관련 기술 개념을 거의 모르거나, 전혀 다른 내용을 답변함

━━━ 2. logical_coherence (논리적 일관성) ━━━
평가 관점: 답변의 구조, STAR 기법(상황-과제-행동-결과) 준수, 인과관계의 명확성
- 90~100: STAR 또는 이에 준하는 구조로 답변하고, 각 단계 간 인과관계가 매우 명확함
- 70~89:  답변에 구조가 있고, 주장과 근거가 연결됨. 일부 비약이 있을 수 있음
- 50~69:  답변의 방향은 맞으나, 구조 없이 나열식이거나 인과관계가 약함
- 30~49:  답변이 산만하고, 질문과 동떨어진 내용이 섞여 있음
- 0~29:   답변이 질문의 의도와 무관하거나, 논리적 연결이 전혀 없음

━━━ 3. communication (소통 능력) ━━━
평가 관점: 설명의 명확성, 구체적 예시 활용, 질문 의도 파악 여부
- 90~100: 질문 의도를 정확히 파악하고, 구체적 예시(코드/경험)를 들어 쉽고 명확하게 설명함
- 70~89:  질문 의도를 파악하고 예시를 1개 이상 활용함. 설명이 대체로 명확함
- 50~69:  질문 의도는 파악했으나, 예시 없이 추상적으로 설명하거나 장황함
- 30~49:  질문 의도를 일부 오해하거나, 설명이 모호하여 이해하기 어려움
- 0~29:   질문을 이해하지 못하거나, 답변을 거의 하지 않음

━━━ 4. problem_solving (문제 해결력) ━━━
평가 관점: 실무 적용 능력, 예외/엣지 케이스 고려, 창의적 접근
- 90~100: 문제를 체계적으로 분석하고, 엣지 케이스(오류 처리, 성능 등)까지 고려하며 대안을 제시함
- 70~89:  실무 적용 가능한 방법을 제시하고, 기본적인 예외 상황을 인지함
- 50~69:  해결 방향은 맞으나, 예외 상황을 고려하지 않거나 피상적인 접근에 그침
- 30~49:  문제 분석 없이 단편적인 답변을 하거나, 실무와 동떨어진 방법을 제시함
- 0~29:   문제를 분석하지 못하거나, 해결 방향을 전혀 제시하지 못함

━━━ overall_score (종합 점수) ━━━
- 4개 차원 점수의 산술 평균을 기본으로 하되, 질문 유형에 따라 ±5점 범위 내 조정 가능
- 예: 기술 질문이면 technical_depth에 가중치, 행동 질문이면 communication에 가중치
"""

        # Different prompt for last vs continuing
        if is_last_question:
            eval_prompt = f"""
            사용자의 답변을 아래 루브릭(채점 기준표)에 따라 엄격하게 평가하세요.
            {scoring_rubric}

            이것이 마지막 질문입니다. next_question은 null로 반환하세요.

            응답 형식 (JSON):
            {{
                "rubric": {{
                    "technical_depth": {{"score": 85, "comment": "채점 근거 1줄"}},
                    "logical_coherence": {{"score": 70, "comment": "채점 근거 1줄"}},
                    "communication": {{"score": 90, "comment": "채점 근거 1줄"}},
                    "problem_solving": {{"score": 60, "comment": "채점 근거 1줄"}}
                }},
                "overall_score": 76,
                "feedback": "종합 피드백 (2-3줄, 강점과 보완점을 구체적으로)",
                "next_question": null
            }}
            """
        else:
            eval_prompt = f"""
            사용자의 답변을 아래 루브릭(채점 기준표)에 따라 엄격하게 평가하세요.
            {scoring_rubric}

            그리고 종합 피드백과 다음 질문을 생성하세요.

            응답 형식 (JSON):
            {{
                "rubric": {{
                    "technical_depth": {{"score": 85, "comment": "채점 근거 1줄"}},
                    "logical_coherence": {{"score": 70, "comment": "채점 근거 1줄"}},
                    "communication": {{"score": 90, "comment": "채점 근거 1줄"}},
                    "problem_solving": {{"score": 60, "comment": "채점 근거 1줄"}}
                }},
                "overall_score": 76,
                "feedback": "종합 피드백 (2-3줄, 강점과 보완점을 구체적으로)",
                "next_question": "다음 질문"
            }}
            """
        
        messages.append({"role": "system", "content": eval_prompt})

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
            # [DEFENSE] AI가 rubric에 불필요한 필드를 넣는 경우 방어 (Whitelist)
            VALID_RUBRIC_KEYS = {'technical_depth', 'logical_coherence', 'communication', 'problem_solving'}
            raw_rubric = result.get('rubric', {})
            rubric = {k: v for k, v in raw_rubric.items() if k in VALID_RUBRIC_KEYS}
            overall_score = result.get('overall_score', 0)
            feedback_text = result.get('feedback', '')
            
            structured_feedback = json.dumps({
                'rubric': rubric,
                'feedback': feedback_text
            }, ensure_ascii=False)
            
            current_exchange.feedback = structured_feedback
            current_exchange.score = overall_score
            current_exchange.save()
            
            # Create Next Question (only if not last)
            next_q = result.get('next_question')
            if next_q and not is_last_question:
                InterviewExchange.objects.create(
                    interview=interview,
                    question=next_q,
                    order=current_exchange.order + 1
                )
            
            # Progress info
            total_answered = interview.exchanges.filter(answer__gt='').count()
            remaining_minutes = None
            if interview.max_minutes:
                elapsed = (timezone.now() - interview.created_at).total_seconds() / 60
                remaining_minutes = max(0, round(interview.max_minutes - elapsed, 1))
            
            return Response({
                "rubric": rubric,
                "overall_score": overall_score,
                "feedback": feedback_text,
                "next_question": next_q if not is_last_question else None,
                "auto_finish": is_last_question,
                "progress": {
                    "answered": total_answered,
                    "max_questions": interview.max_questions,
                    "remaining_minutes": remaining_minutes,
                    "max_minutes": interview.max_minutes,
                }
            })

        except Exception as e:
            print(f"OpenAI Error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='finish')
    def finish_interview(self, request, pk=None):
        """
        [면접 종료 및 AI 종합 결과 리포트 생성]
        - 모든 교환의 Rubric 점수를 집계
        - 차원별 평균 점수 + AI 종합 분석 리포트 생성
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
        
        # ── 캐시 확인: AI 분석은 비싸므로 캐싱 ──
        cached_report = None
        if interview.report_data:
            try:
                cached_report = json.loads(interview.report_data)
            except (json.JSONDecodeError, TypeError):
                cached_report = None

        if cached_report:
            # AI 분석은 캐시에서 가져오고, 스킬 데이터만 실시간 갱신
            ai_summary = cached_report.get('ai_summary')
            dimension_averages = cached_report.get('dimensions', {})
            overall_avg = cached_report.get('overall_average', 0)
            best_answer = cached_report.get('best_answer', {})
            needs_improvement = cached_report.get('needs_improvement', {})
            duration_minutes = cached_report.get('duration_minutes', 0)
        else:
            # 최초 생성: 점수 집계 + AI 호출
            dimensions = {
                'technical_depth': {'scores': [], 'label': '기술적 깊이'},
                'logical_coherence': {'scores': [], 'label': '논리적 일관성'},
                'communication': {'scores': [], 'label': '소통 능력'},
                'problem_solving': {'scores': [], 'label': '문제 해결력'}
            }
            
            overall_scores = []
            best_exchange = None
            worst_exchange = None
            qa_pairs = []
            
            for ex in exchanges:
                overall_scores.append(ex.score)
                qa_pairs.append({"question": ex.question[:200], "answer": ex.answer[:200], "score": ex.score})
                
                if best_exchange is None or ex.score > best_exchange.score:
                    best_exchange = ex
                if worst_exchange is None or ex.score < worst_exchange.score:
                    worst_exchange = ex
                
                try:
                    feedback_data = json.loads(ex.feedback)
                    rubric = feedback_data.get('rubric', {})
                    for dim_key in dimensions:
                        if dim_key in rubric:
                            dimensions[dim_key]['scores'].append(rubric[dim_key].get('score', 0))
                except (json.JSONDecodeError, TypeError):
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
            
            # AI 종합 리포트 생성 (비용 발생 → 최초 1회만)
            ai_summary = None
            try:
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                
                dim_summary = "\n".join([
                    f"- {v['label']}: 평균 {v['average']}점"
                    for v in dimension_averages.values()
                ])
                
                qa_summary = "\n".join([
                    f"Q{i+1}: {qa['question'][:100]}\nA: {qa['answer'][:100]}\n점수: {qa['score']}"
                    for i, qa in enumerate(qa_pairs[:10])
                ])
                
                summary_prompt = f"""
                면접 결과를 종합 분석하여 실용적인 리포트를 작성하세요.
                
                [면접관 유형]: {interview.get_persona_display()}
                [총 질문 수]: {exchanges.count()}
                [종합 평균 점수]: {overall_avg}점
                
                [차원별 평균]
                {dim_summary}
                
                [질의응답 요약]
                {qa_summary}
                
                다음 항목을 포함한 리포트를 JSON으로 작성하세요:
                {{
                    "grade": "S/A/B/C/D/F 중 하나 (S: 95+, A: 85+, B: 70+, C: 55+, D: 40+, F: 40미만)",
                    "one_line_summary": "면접 결과 한 줄 요약",
                    "strengths": ["강점1", "강점2", "강점3"],
                    "weaknesses": ["약점1", "약점2"],
                    "improvement_tips": ["구체적 개선 팁1", "구체적 개선 팁2", "구체적 개선 팁3"],
                    "recommended_study": ["보완 학습 주제1", "보완 학습 주제2"]
                }}
                """
                
                ai_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "당신은 IT 채용 전문 면접 코치입니다. 면접 결과를 분석하여 실용적인 개선 방향을 제시합니다."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                ai_summary = json.loads(ai_response.choices[0].message.content)
            except Exception as e:
                print(f"AI Summary Error (non-critical): {e}")
                ai_summary = None
            
            duration_minutes = round((timezone.now() - interview.created_at).total_seconds() / 60, 1)
            best_answer = {
                'question': best_exchange.question[:100] if best_exchange else '',
                'score': best_exchange.score if best_exchange else 0
            }
            needs_improvement = {
                'question': worst_exchange.question[:100] if worst_exchange else '',
                'score': worst_exchange.score if worst_exchange else 0
            }
        
        # ── 스킬 데이터는 매번 실시간 계산 (DB 쿼리만, API 비용 없음) ──
        from learning.models import StudentChecklist, LearningObjective, Lecture

        enrolled_lectures = Lecture.objects.filter(students=interview.student)
        all_objectives = LearningObjective.objects.filter(
            syllabus__lecture__in=enrolled_lectures
        ).select_related('syllabus', 'syllabus__lecture')

        total_count = all_objectives.count()
        earned_ids = set(
            StudentChecklist.objects.filter(
                student=interview.student, is_checked=True
            ).values_list('objective_id', flat=True)
        )
        earned_count = len(earned_ids & set(all_objectives.values_list('id', flat=True)))

        category_stats = {}
        for obj in all_objectives:
            lec_title = obj.syllabus.lecture.title
            if lec_title not in category_stats:
                category_stats[lec_title] = {'name': lec_title, 'earned': 0, 'total': 0, 'percent': 0}
            category_stats[lec_title]['total'] += 1
            if obj.id in earned_ids:
                category_stats[lec_title]['earned'] += 1

        for cat in category_stats.values():
            cat['percent'] = round(cat['earned'] / cat['total'] * 100) if cat['total'] > 0 else 0
        
        # 미획득 학습 목표를 낮은 주차 순으로 추천 (선행 학습 우선)
        not_earned_objectives = all_objectives.exclude(
            id__in=earned_ids
        ).order_by('syllabus__week_number', 'id')[:5]
        recommended_skills = [
            {
                'name': obj.content,
                'category': obj.syllabus.lecture.title,
                'level': 1,
                'hint': f"{obj.syllabus.week_number}주차 학습 목표를 완료하면 획득!"
            }
            for obj in not_earned_objectives
        ]

        skill_progress = round(earned_count / total_count * 100) if total_count > 0 else 0

        # ── 최종 리포트 조립 ──
        report = {
            'interview_id': interview.id,
            'persona': interview.get_persona_display(),
            'total_questions': exchanges.count(),
            'duration_minutes': duration_minutes,
            'max_questions': interview.max_questions,
            'max_minutes': interview.max_minutes,
            'overall_average': overall_avg,
            'dimensions': dimension_averages,
            'ai_summary': ai_summary,
            'best_answer': best_answer,
            'needs_improvement': needs_improvement,
            'skill_connection': {
                'earned_count': earned_count,
                'total_count': total_count,
                'progress_percent': skill_progress,
                'category_stats': category_stats,
                'recommended_skills': recommended_skills,
            },
            'disclaimer': '⚠️ 본 평가는 AI가 자동 생성한 참고 자료이며, 전문가 검증을 거치지 않았습니다. STAR 기법 및 업계 통용 면접 평가 프레임워크를 참고하였으나, 실제 채용 면접의 공식 평가로 사용될 수 없습니다.'
        }
        
        # AI 분석 결과를 DB에 캐싱 (스킬 데이터 포함, 다음에 AI 부분만 재사용)
        interview.report_data = json.dumps(report, ensure_ascii=False)
        interview.save(update_fields=['report_data'])
        
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
