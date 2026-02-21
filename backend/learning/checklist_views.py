"""
체크리스트 및 동적 경로 재설계 Views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Lecture, Syllabus, LearningObjective, StudentChecklist
from .serializers import SyllabusSerializer


class ChecklistViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        lecture_id = request.query_params.get('lecture_id')
        if not lecture_id:
            return Response({"error": "lecture_id required"}, status=400)

        lecture = get_object_or_404(Lecture, id=lecture_id)

        # Check enrollment
        if not lecture.students.filter(id=request.user.id).exists() and lecture.instructor != request.user:
             return Response({"error": "Not enrolled"}, status=403)

        syllabi = Syllabus.objects.filter(lecture=lecture)
        serializer = SyllabusSerializer(syllabi, many=True, context={'request': request})
        return Response(serializer.data)

    # POST /api/learning/checklist/<objective_id>/toggle/
    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        objective = get_object_or_404(LearningObjective, id=pk)

        lecture = objective.syllabus.lecture
        if not lecture.students.filter(id=request.user.id).exists():
             return Response({"error": "Not enrolled"}, status=403)

        checklist, created = StudentChecklist.objects.get_or_create(student=request.user, objective=objective)
        checklist.is_checked = not checklist.is_checked
        checklist.save()

        return Response({"id": objective.id, "is_checked": checklist.is_checked})

    # GET /api/learning/checklist/analyze/?lecture_id=<id>
    # [Dynamic Re-routing Engine]
    @action(detail=False, methods=['get'])
    def analyze(self, request):
        lecture_id = request.query_params.get('lecture_id')
        if not lecture_id:
            return Response({"error": "lecture_id required"}, status=400)

        lecture = get_object_or_404(Lecture, id=lecture_id)

        # 1. Calculate Progress
        total_objectives = LearningObjective.objects.filter(syllabus__lecture=lecture).count()
        if total_objectives == 0:
            return Response({"status": "clean", "progress": 0, "message": "아직 학습 목표가 없습니다."})

        checked_count = StudentChecklist.objects.filter(
            student=request.user,
            objective__syllabus__lecture=lecture,
            is_checked=True
        ).count()

        progress = (checked_count / total_objectives) * 100

        # 2. Determine Status (Simple Heuristic for MVP)
        result_status = "good"
        recommendation = None

        if progress < 30:
            result_status = "critical"
            recommendation = {
                "type": "catch_up",
                "title": "🚨 경로 이탈 위험!",
                "message": "진도율이 너무 낮습니다 (30% 미만). AI가 핵심 요약 코스로 경로를 재설정할까요?",
                "action": "압축 코스 생성"
            }
        elif progress < 60:
            result_status = "warning"
            recommendation = {
                "type": "review",
                "title": "⚠️ 학습 지연 감지",
                "message": "계획보다 뒤쳐지고 있습니다. 놓친 핵심 개념만 빠르게 훑어보세요.",
                "action": "빠른 복습 하기"
            }
        else:
            result_status = "good"
            recommendation = {
                "type": "keep_going",
                "title": "✅ 순항 중",
                "message": "훌륭합니다! 현재 속도를 유지하세요.",
                "action": None
            }

        return Response({
            "progress": round(progress, 1),
            "status": result_status,
            "recommendation": recommendation
        })

    # POST /api/learning/checklist/recovery_plan/
    # [Dynamic Re-routing Action]
    @action(detail=False, methods=['post'])
    def recovery_plan(self, request):
        lecture_id = request.data.get('lecture_id')
        if not lecture_id:
            return Response({"error": "lecture_id required"}, status=400)

        lecture = get_object_or_404(Lecture, id=lecture_id)

        # 1. Collect unfinished objectives
        unfinished_objectives = LearningObjective.objects.filter(
            syllabus__lecture=lecture
        ).exclude(
            student_checks__student=request.user,
            student_checks__is_checked=True
        )

        if not unfinished_objectives.exists():
            return Response({"message": "모든 학습 목표를 달성했습니다! 복구할 내용이 없습니다."})

        # 2. Format for AI Prompt
        objective_texts = "\n".join([f"- {obj.content}" for obj in unfinished_objectives])

        # 3. Call OpenAI
        from django.conf import settings
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        system_prompt = (
            "당신은 '학습 경로 재설계 전문가'입니다.\n"
            "학생이 놓친 학습 목표들을 바탕으로, 단기간에 캐치업할 수 있는 '핵심 압축 가이드'를 작성해주세요.\n"
            "반드시 아래 Markdown 형식을 따라주세요:\n\n"
            "# 🚀 3분 압축 복구 플랜\n\n"
            "## 1. 지금 꼭 알아야 할 핵심 개념\n"
            "(놓친 항목들의 핵심 정의를 3줄 요약)\n\n"
            "## 2. 실무 적용 포인트\n"
            "(해당 개념이 왜 중요한지, 어떻게 쓰이는지 간단 설명)\n\n"
            "## 3. 추천 학습 순서\n"
            "1. (가장 먼저 봐야 할 것)\n"
            "2. (그 다음 순서)\n"
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음은 학생이 아직 학습하지 못한 목표들입니다. 이를 위한 복구 플랜을 짜주세요:\n\n{objective_texts}"}
                ],
                max_tokens=1000
            )
            recovery_content = response.choices[0].message.content

            return Response({
                "status": "success",
                "recovery_plan": recovery_content,
                "unfinished_count": unfinished_objectives.count()
            })

        except Exception as e:
            print(f"OPENAI API Error: {str(e)}")
            # Fallback for Demo/Error cases
            fallback_plan = (
                "# 🚀 [임시] 3분 압축 복구 플랜\n"
                "(AI 서비스 연결이 원활하지 않아 자동 생성된 임시 플랜입니다.)\n\n"
                "## 1. 놓친 핵심 개념 요약\n"
            )
            for obj in unfinished_objectives[:3]:
                 fallback_plan += f"- **{obj.content}**: 이 개념은 반드시 숙지해야 합니다.\n"

            fallback_plan += "\n## 2. 추천 학습 경로\n1. 공식 문서 빠르게 훑어보기\n2. 예제 코드 실행해보기\n"

            return Response({
                "status": "success",
                "recovery_plan": fallback_plan,
                "unfinished_count": unfinished_objectives.count(),
                "is_fallback": True
            })
