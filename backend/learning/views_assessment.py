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

        # 3. GPT에게 퀴즈 생성 요청
        try:
            quiz_data = self._generate_quiz_from_ai(full_context_text)
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
            
            # [AI Review Generation] 틀린 문제가 있으면 오답노트 생성
            failed_details = AttemptDetail.objects.filter(attempt=attempt, is_correct=False).select_related('question')
            
            if failed_details.exists():
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    
                    review_prompt = "다음은 학생이 퀴즈에서 틀린 문제들입니다. 틀린 이유를 분석하고, 핵심 개념을 보충 설명해주세요.\n\n"
                    for detail in failed_details:
                        q = detail.question
                        review_prompt += f"[문제] {q.question_text}\n"
                        review_prompt += f"- 학생 답: {detail.student_answer}\n"
                        review_prompt += f"- 정답: {q.correct_answer}\n"
                        # 기존 explanation이 있다면 참고용으로 추가
                        # review_prompt += f"- 참고: {q.explanation}\n"
                        review_prompt += "\n"
                        
                    review_prompt += """
                    [요청사항]
                    1. 각 문제별로 '💡 오답 분석'과 '📚 핵심 요약'을 제공하세요.
                    2. 학생이 헷갈려할 만한 부분을 짚어주세요.
                    3. Markdown 형식으로 가독성 있게 작성하세요.
                    """
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "당신은 IT 교육 전문가입니다. 친절하고 명확하게 오답을 풀이해주세요."},
                            {"role": "user", "content": review_prompt}
                        ]
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

    def _generate_quiz_from_ai(self, text):
        """
        GPT Output Format: JSON List
        """
        # [Validation] 텍스트가 너무 짧으면 엉뚱한 문제가 나올 수 있음
        text_len = len(text)
        print(f"DEBUG: Quiz Generation Context Length: {text_len}")
        print(f"DEBUG: Context Preview: {text[:100]}...")
        
        # [Relaxed] 25분 영상도 자막 밀도가 낮으면 글자수가 적을 수 있음 -> 200자로 완화
        if text_len < 200:
             raise ValueError(f"학습 내용이 부족하여 퀴즈를 생성할 수 없습니다. (현재 {text_len}자, 최소 200자 필요)")

        system_prompt = """
        너는 '학습 내용 기반 퀴즈 생성 전문가'야.
        제공된 [학습 텍스트]를 바탕으로 학습자가 내용을 잘 이해했는지 확인하는 퀴즈를 출제해.
        
        [원칙]
        1. 텍스트에 명시된 내용(팩트)에 기반하여 문제를 낼 것.
        2. '없는 내용'을 창조하지 말 것.
        3. 만약 내용이 조금 부족하더라도, 텍스트에 등장하는 핵심 단어나 개념을 활용하여 어떻게든 5문제를 만들어.
        4. 문제를 만들기 정 어렵다면, 같은 내용을 다르게 물어보는 방식으로라도 5문제를 채울 것.
        5. [중요] 모든 질문, 보기, 정답, 해설은 반드시 '한국어(Korean)'로 작성해야 해. (영어 금지)
        """

        user_prompt = f"""
        다음 [학습 텍스트]를 읽고 객관식 퀴즈 5문제를 만들어줘.
        
        [제약 사항]
        1. 문항 수: 5개 (필수)
        2. 포맷: JSON 배열 (마크다운 없이)
        3. 구조: question, options(4개), answer, explanation
        4. 정답(answer)은 options 중 하나와 정확히 일치해야 함.
        5. 언어: 무조건 한국어 (영어 질문/보기 금지)

        [학습 텍스트]
        {text}
        
        [JSON 출력 예시]
        [
            {{
                "question": "Vue.js의 핵심 기능은?",
                "options": ["양방향 바인딩", "서버 렌더링", "데이터베이스", "운영체제"],
                "answer": "양방향 바인딩",
                "explanation": "본문에 따르면..."
            }}
        ]
        """
        
        from django.conf import settings
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3, # 약간 창의성 허용 (0.2 -> 0.3)
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSON 파싱 (마크다운 코드블럭 제거 처리)
        if content.startswith("```json"):
            content = content.replace("```json", "").split("```")[0]
        elif content.startswith("```"):
            content = content.replace("```", "").split("```")[0]
            
        try:
            quiz_list = json.loads(content)
            if not quiz_list:
                # 그래도 비어있다면
                raise ValueError("AI가 퀴즈를 생성하지 못했습니다. (내용 부족 또는 포맷 오류)")
            return quiz_list
        except json.JSONDecodeError:
            print(f"JSON Parse Error. Raw Content: {content}")
            raise ValueError("AI 응답 형식이 올바르지 않습니다.")
