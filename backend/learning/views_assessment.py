from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import LearningSession, STTLog, SessionSummary, DailyQuiz, QuizQuestion, QuizAttempt, AttemptDetail
from .serializers import LearningSessionSerializer, STTLogSerializer, SessionSummarySerializer, DailyQuizSerializer, QuizAttemptSerializer
from django.utils import timezone
from django.db import transaction
from django.db.models import Q # Added Q
import openai
import os
import json
from django.conf import settings # [FIX] Import settings

openai.api_key = os.getenv('OPENAI_API_KEY')

class AssessmentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='generate-daily-quiz')
    def generate_daily_quiz(self, request):
        """
        오늘의 학습 내용을 바탕으로 5문제 퀴즈 생성
        Optional: body에 'session_id'를 포함하면 해당 세션으로만 생성
        """
        user = request.user
        today = timezone.now().date()
        
        # [Explicit Session ID Handling]
        requested_session_id = request.data.get('session_id')
        
        target_session = None
        
        if requested_session_id:
            try:
                # [Fix] Allow shared sessions (completed + same lecture enrollment)
                target_session = LearningSession.objects.filter(
                    Q(student=user) | 
                    Q(lecture__students=user, is_completed=True)
                ).distinct().get(id=requested_session_id)
                print(f"DEBUG: Using requested session ID: {target_session.id}")
            except LearningSession.DoesNotExist:
                return Response({"error": "요청한 세션을 찾을 수 없거나 권한이 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        else:
            # 1. 이미 오늘 퀴즈가 있는지 확인 (세션 지정이 없을 때만 체크 - 세션 지정 시에는 재생성 의도로 간주 가능하지만, 일단 유지)
            # if DailyQuiz.objects.filter(student=user, quiz_date=today).exists(): ... 
            # (User might want to regenerate for a specific new session, so better to skip this check if session_id is provided? 
            #  For safety, let's keep the check mainly for "Daily" quiz concept, but maybe we want "Session Quiz"?
            #  The requirement says "Generate Daily Quiz". Let's stick to logic but prioritize explicit session.)
            
            # 2. 최근 24시간 이내 학습한 세션 가져오기
            one_day_ago = timezone.now() - timezone.timedelta(days=1)
            sessions = LearningSession.objects.filter(student=user, start_time__gte=one_day_ago).order_by('-start_time')
            
            if not sessions.exists():
                 return Response({"error": "최근 학습 기록이 없어 퀴즈를 만들 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
            
            target_session = sessions.first()
            print(f"DEBUG: Found latest session: {target_session.id}")

        # [Content Extraction]
        # [Fallback Logic] 요약본이 있으면 요약본 사용, 없으면 STT 로그 사용
        summaries = SessionSummary.objects.filter(session=target_session)
        if summaries.exists():
            full_context_text = "\n".join([s.content_text for s in summaries])
            print("DEBUG: Using existing summaries.")
        else:
            # 요약본이 없으면 STT 원문 텍스트 수집
            stt_logs = STTLog.objects.filter(session=target_session).order_by('sequence_order')
            full_context_text = "\n".join([log.text_chunk for log in stt_logs])
            print(f"DEBUG: Using raw STT logs. Total length: {len(full_context_text)}")

        if not full_context_text:
             return Response({"error": "오늘 학습한 내용(자막/요약)이 없어 퀴즈를 만들 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 3. GPT에게 퀴즈 생성 요청 (RAG 포함)
        try:
            quiz_data = self._generate_quiz_from_ai(full_context_text, lecture_id=target_session.lecture_id)
        except Exception as e:
            return Response({"error": f"AI 퀴즈 생성 실패: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. DB 저장 (Transaction)
        with transaction.atomic():
            # [Fix] Use target_session instead of 'sessions' (which might be undefined)
            target_section = target_session.section if target_session else None
            
            if not target_section:
                # Fallback: DB에서 아무 섹션이나 하나 가져오거나, 없으면 에러 (혹은 더미 생성)
                # 여기서는 가장 간단하게 첫 번째 섹션을 가져옵니다.
                from courses.models import CourseSection
                target_section = CourseSection.objects.first()
                
                # 만약 섹션이 아예 하나도 없다면? (초기 상태) -> 더미 섹션 생성
                if not target_section:
                    target_section = CourseSection.objects.create(
                        title="일반 학습",
                        day_sequence=1,
                        description="자동 생성된 기본 섹션"
                    )
                    print("DEBUG: Created dummy section for quiz.")

            daily_quiz = DailyQuiz.objects.create(
                student=user,
                section=target_section,
                total_score=0,
                is_passed=False
            )
            
            for q_idx, q_item in enumerate(quiz_data):
                QuizQuestion.objects.create(
                    quiz=daily_quiz,
                    question_text=q_item['question'],
                    options=q_item['options'], # List[str]
                    correct_answer=q_item['answer'],
                    explanation=q_item.get('explanation', '')
                )
                
        return Response(DailyQuizSerializer(daily_quiz).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit_quiz(self, request, pk=None):
        """
        퀴즈 답안 제출 및 채점
        Request: { "answers": { "question_id_1": "1번답", "question_id_2": "2번답" ... } }
        """
        try:
            quiz = DailyQuiz.objects.get(id=pk, student=request.user)
        except DailyQuiz.DoesNotExist:
            return Response({"error": "퀴즈를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
            
        student_answers = request.data.get('answers', {})
        total_questions = quiz.questions.count()
        correct_count = 0
        
        # 이미 푼 기록이 있다면 리턴 (중복 풀이 방지 정책 시)
        # if QuizAttempt.objects.filter(quiz=quiz, student=request.user).exists(): ...

        with transaction.atomic():
            attempt = QuizAttempt.objects.create(
                quiz=quiz, 
                student=request.user, 
                score=0 # 임시
            )
            
            questions = quiz.questions.all()
            for question in questions:
                s_answer = str(student_answers.get(str(question.id), "")).strip()
                is_correct = (s_answer == question.correct_answer)
                
                if is_correct:
                    correct_count += 1
                
                AttemptDetail.objects.create(
                    attempt=attempt,
                    question=question,
                    student_answer=s_answer,
                    is_correct=is_correct
                )
            
            # 100점 만점 환산
            final_score = int((correct_count / total_questions) * 100) if total_questions > 0 else 0
            attempt.score = final_score
            
            # [AI Review Generation] 틀린 문제가 있으면 오답노트 생성 (RAG 포함)
            failed_details = AttemptDetail.objects.filter(attempt=attempt, is_correct=False).select_related('question')
            
            if failed_details.exists():
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    
                    review_prompt = "다음은 학생이 퀴즈에서 틀린 문제들입니다. 틀린 이유를 분석하고, 핵심 개념을 보충 설명해주세요.\n\n"
                    question_keywords = []
                    for detail in failed_details:
                        q = detail.question
                        review_prompt += f"[문제] {q.question_text}\n"
                        review_prompt += f"- 학생 답: {detail.student_answer}\n"
                        review_prompt += f"- 정답: {q.correct_answer}\n\n"
                        question_keywords.append(q.question_text)

                    # [RAG] 틀린 문제 키워드로 공식 문서 검색
                    rag_context = ""
                    try:
                        from .rag import RAGService
                        rag = RAGService()
                        search_query = " ".join(question_keywords)[:500]
                        lecture_id = quiz.section.course.lectures.first().id if hasattr(quiz, 'section') and quiz.section else None
                        related_docs = rag.search(query=search_query, top_k=3, lecture_id=lecture_id)
                        if related_docs:
                            rag_context = "\n".join([f"- {doc.content[:300]}" for doc in related_docs])
                            print(f"✅ [RAG] 오답노트 생성에 공식 문서 {len(related_docs)}건 참조")
                    except Exception as rag_err:
                        print(f"⚠️ [RAG] 오답노트 검색 실패: {rag_err}")

                    review_prompt += """
                    [요청사항]
                    1. 각 문제별로 '💡 오답 분석'과 '📚 핵심 요약'을 제공하세요.
                    2. 학생이 헷갈려할 만한 부분을 짚어주세요.
                    3. Markdown 형식으로 가독성 있게 작성하세요.
                    """
                    if rag_context:
                        review_prompt += f"\n[공식 문서 참조 (정확한 설명 근거)]:\n{rag_context}"
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "당신은 IT 교육 전문가입니다. 공식 문서 참조가 있으면 이를 근거로 친절하고 명확하게 오답을 풀이해주세요."},
                            {"role": "user", "content": review_prompt}
                        ],
                        max_tokens=2000,
                    )
                    attempt.review_note = response.choices[0].message.content
                    
                except Exception as e:
                    print(f"AI Review Generation Failed: {e}")
                    attempt.review_note = "오답노트 생성에 실패했습니다. (서버 오류)"
            
            else:
                attempt.review_note = "🎉 축하합니다! 모든 문제를 맞히셨습니다. 완벽해요!"

            attempt.save()
            
            # 퀴즈 메인 점수 업데이트 (최근 점수 반영)
            quiz.total_score = final_score
            quiz.is_passed = (final_score >= 80) # 80점 이상 통과
            quiz.save()
            
        return Response(QuizAttemptSerializer(attempt).data, status=status.HTTP_200_OK)

    def _generate_quiz_from_ai(self, text, lecture_id=None):
        """
        GPT Output Format: JSON List (RAG 통합)
        """
        # [Validation] 텍스트가 너무 짧으면 엉뚱한 문제가 나올 수 있음
        text_len = len(text)
        print(f"DEBUG: Quiz Generation Context Length: {text_len}")
        print(f"DEBUG: Context Preview: {text[:100]}...")
        
        # [Relaxed] 25분 영상도 자막 밀도가 낮으면 글자수가 적을 수 있음 -> 200자로 완화
        if text_len < 200:
             raise ValueError(f"학습 내용이 부족하여 퀴즈를 생성할 수 없습니다. (현재 {text_len}자, 최소 200자 필요)")

        # [RAG] 공식 문서에서 관련 컨텍스트 검색
        rag_context = ""
        try:
            from .rag import RAGService
            rag = RAGService()
            search_query = text[:500]
            related_docs = rag.search(query=search_query, top_k=3, lecture_id=lecture_id)
            if related_docs:
                rag_context = "\n".join([f"- {doc.content[:300]}" for doc in related_docs])
                print(f"✅ [RAG] 퀴즈 생성에 공식 문서 {len(related_docs)}건 참조")
        except Exception as rag_err:
            print(f"⚠️ [RAG] 검색 실패 (퀴즈는 학습 텍스트만으로 진행): {rag_err}")

        system_prompt = (
            "너는 '학습 내용 기반 퀴즈 생성 전문가'야.\n"
            "제공된 [학습 텍스트]와 [공식 문서 참조]를 바탕으로 학습자가 내용을 잘 이해했는지 확인하는 퀴즈를 출제해.\n\n"
            "[원칙]\n"
            "1. 텍스트에 명시된 내용(팩트)에 기반하여 문제를 낼 것.\n"
            "2. '없는 내용'을 창조하지 말 것.\n"
            "3. [공식 문서 참조]가 제공되면, 전문 용어의 정확한 정의에 기반한 문제를 포함할 것.\n"
            "4. 내용이 부족하더라도 핵심 단어나 개념을 활용하여 5문제를 만들어.\n"
            "5. [중요] 모든 질문, 보기, 정답, 해설은 반드시 '한국어(Korean)'로 작성해야 해. (영어 금지)\n\n"
            "[출력 형식] 반드시 아래 JSON 구조로 응답하세요:\n"
            '{"questions": [{"question": "...", "options": ["A","B","C","D"], "answer": "정답 보기 문자열", "explanation": "해설"}]}\n'
            "- questions 배열에 정확히 5개의 문항을 포함할 것\n"
            "- answer는 반드시 options 중 하나와 정확히 일치할 것"
        )

        user_prompt = f"[학습 텍스트]\n{text}"
        if rag_context:
            user_prompt += f"\n\n[공식 문서 참조 (정확한 정의 및 예시)]\n{rag_context}"
        user_prompt += "\n\n위 텍스트를 기반으로 객관식 퀴즈 5문제를 JSON으로 생성하세요."
        
        from django.conf import settings
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content.strip()
        
        try:
            parsed = json.loads(content)
            # response_format 사용 시 {"questions": [...]} 구조
            quiz_list = parsed.get('questions', parsed) if isinstance(parsed, dict) else parsed
            if isinstance(quiz_list, dict):
                # 첫 번째 list 값을 찾음
                for v in parsed.values():
                    if isinstance(v, list):
                        quiz_list = v
                        break
            if not quiz_list:
                raise ValueError("AI가 퀴즈를 생성하지 못했습니다. (내용 부족 또는 포맷 오류)")
            return quiz_list
        except json.JSONDecodeError:
            print(f"JSON Parse Error. Raw Content: {content}")
            raise ValueError("AI 응답 형식이 올바르지 않습니다.")
