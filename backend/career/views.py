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
            
        # 2.5 획득한 스킬 (Checklist)
        from learning.models import StudentChecklist
        skills_qs = StudentChecklist.objects.filter(
            student=user, is_checked=True
        ).select_related('objective', 'objective__syllabus__lecture')
        
        skill_texts = [f"- {s.objective.content} ({s.objective.syllabus.lecture.title})" for s in skills_qs]
        skills_block = "\n".join(skill_texts) if skill_texts else "아직 획득한 스킬 블록이 없습니다."
            
        # 3. 프롬프트 구성
        if p_type == 'JOB':
            system_prompt = "당신은 IT 전문 커리어 컨설턴트입니다. 학생의 학습 기록과 획득한 스킬을 바탕으로 구직용 포트폴리오를 작성해주세요."
            user_prompt = f"""
            학생의 다음 학습 요약, 획득한 기술 스택(Skills), 성취도를 바탕으로 Markdown 형식의 포트폴리오를 작성해주세요.
            
            [획득한 기술 스택 (Verified Skills)]
            {skills_block}

            [학습 기록 (Summaries)]
            {all_text[:3000]} 
            
            [평균 퀴즈 점수]
            {avg_score}점
            
            [요청 사항]
            - 전문적인 어조 사용
            - '핵심 역량(Key Skills)' 섹션에 위 기술 스택을 잘 녹여낼 것
            - '학습 프로젝트 경험' 및 '자기소개서' 포함
            """
            default_title = f"IT 개발자 취업 포트폴리오 ({timezone.now().strftime('%Y-%m-%d')})"
        else:
            system_prompt = "당신은 스타트업 액셀러레이터의 멘토입니다. 학생이 배운 기술을 활용하여 구현 가능한 MVP 기술 명세서를 작성해주세요."
            user_prompt = f"""
            학생이 보유한 다음 기술 스택과 학습 기록을 바탕으로, 실제 창업 시 구현 가능한 MVP(Minimum Viable Product) 기술 기획서를 작성해주세요.
            
            [보유 기술 스택]
            {skills_block}
            
            [학습 기록]
            {all_text[:3000]}
            
            [요청 사항]
            - 서비스 아이디어 제안 (보유 기술을 활용할 수 있는 아이템)
            - 필요한 기술 스택 (Frontend, Backend, DB 등)
            - 핵심 기능 명세
            - 4주 개발 로드맵
            """
            default_title = f"스타트업 MVP 기술 기획서 ({timezone.now().strftime('%Y-%m-%d')})"

        # 4. AI 호출
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            generated_content = response.choices[0].message.content
            
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

    @action(detail=False, methods=['get'], url_path='skills')
    def skills(self, request):
        """
        [Skill Block Gamification]
        획득한 스킬 + 추가 획득 가능한 스킬 + 전체 진행률을 반환.
        학생이 "다음에 뭘 해야 하는지" 동기부여를 제공.
        """
        from learning.models import StudentChecklist, LearningObjective, Syllabus, Lecture

        user = request.user

        # 수강 중인 강의 조회
        enrolled_lectures = Lecture.objects.filter(students=user)
        if not enrolled_lectures.exists():
            return Response({"stats": {"total": 0, "earned": 0, "rate": 0}, "categories": []})

        # 전체 학습 목표 (수강 중인 강의의 모든 목표)
        all_objectives = LearningObjective.objects.filter(
            syllabus__lecture__in=enrolled_lectures
        ).select_related('syllabus', 'syllabus__lecture').order_by(
            'syllabus__lecture__title', 'syllabus__week_number', 'id'
        )

        # 획득한 목표 ID Set
        earned_ids = set(
            StudentChecklist.objects.filter(
                student=user, is_checked=True
            ).values_list('objective_id', flat=True)
        )

        # 강의별 그룹핑
        categories_map = {}  # {lecture_title: {"earned": [...], "available": [...]}}

        for obj in all_objectives:
            lecture_title = obj.syllabus.lecture.title
            week_num = obj.syllabus.week_number
            is_earned = obj.id in earned_ids

            if lecture_title not in categories_map:
                categories_map[lecture_title] = {"earned": [], "available": []}

            item = {
                "id": obj.id,
                "name": obj.content,
                "week": f"{week_num}주차",
                "source": f"{week_num}주차 수업",
            }

            if is_earned:
                # 획득한 날짜 조회
                check = StudentChecklist.objects.filter(
                    student=user, objective=obj, is_checked=True
                ).first()
                item["date"] = check.updated_at.strftime('%Y-%m-%d') if check else ""
                categories_map[lecture_title]["earned"].append(item)
            else:
                item["hint"] = f"{week_num}주차 학습 목표를 완료하면 획득!"
                categories_map[lecture_title]["available"].append(item)

        # 결과 조립
        total_count = all_objectives.count()
        earned_count = len(earned_ids & set(all_objectives.values_list('id', flat=True)))
        rate = round((earned_count / total_count) * 100) if total_count > 0 else 0

        categories = []
        for lecture_title, groups in categories_map.items():
            cat_total = len(groups["earned"]) + len(groups["available"])
            cat_earned = len(groups["earned"])
            categories.append({
                "category": lecture_title,
                "earned": groups["earned"],
                "available": groups["available"],
                "total": cat_total,
                "earned_count": cat_earned,
                "rate": round((cat_earned / cat_total) * 100) if cat_total > 0 else 0,
            })

        return Response({
            "stats": {
                "total": total_count,
                "earned": earned_count,
                "rate": rate,
            },
            "categories": categories,
        })
