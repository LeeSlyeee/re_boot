"""
Phase 1: 수준 진단 + 갭 맵 API
- 진단 테스트 (Placement Quiz)
- 목표 설정 (Goal Anchoring)
- 갭 맵 (Gap Map)
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg, Q

from .models import (
    Skill, CareerGoal, PlacementQuestion, PlacementResult,
    StudentGoal, StudentSkill, Lecture
)


class PlacementViewSet(viewsets.ViewSet):
    """진단 테스트 관련 API"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='questions')
    def get_questions(self, request):
        """GET /api/learning/placement/questions/ → 진단 문항 전체 조회"""
        questions = PlacementQuestion.objects.all()
        data = [
            {
                'id': q.id,
                'question_text': q.question_text,
                'options': q.options,
                'category': q.category,
                'difficulty': q.difficulty,
                'order': q.order,
            }
            for q in questions
        ]
        return Response(data)

    @action(detail=False, methods=['post'], url_path='submit')
    def submit(self, request):
        """
        POST /api/learning/placement/submit/
        Body: { "answers": { "1": "선택A", "2": "선택B", ... }, "lecture_id": 1 (선택) }
        """
        answers = request.data.get('answers', {})
        lecture_id = request.data.get('lecture_id')

        if not answers:
            return Response({'error': 'answers는 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 채점
        questions = PlacementQuestion.objects.all()
        total = questions.count()
        correct = 0
        category_scores = {'CONCEPT': 0, 'PRACTICE': 0, 'PATTERN': 0}
        category_totals = {'CONCEPT': 0, 'PRACTICE': 0, 'PATTERN': 0}

        for q in questions:
            category_totals[q.category] = category_totals.get(q.category, 0) + 1
            user_answer = answers.get(str(q.id), '')
            if user_answer == q.correct_answer:
                correct += 1
                category_scores[q.category] = category_scores.get(q.category, 0) + 1

        # 레벨 판정
        if total == 0:
            ratio = 0
        else:
            ratio = correct / total

        if ratio >= 0.7:
            level = 3  # 실습 경험자
        elif ratio >= 0.4:
            level = 2  # 기초 이해자
        else:
            level = 1  # 완전 초보

        # 결과 저장
        result = PlacementResult.objects.create(
            student=request.user,
            lecture_id=lecture_id,
            level=level,
            score=correct,
            total_questions=total,
            answers=answers,
            category_scores=category_scores,
        )

        # 진단 결과 기반으로 초기 갭 맵 생성
        _initialize_gap_map(request.user, level)

        return Response({
            'id': result.id,
            'level': level,
            'level_label': dict(PlacementResult.LEVEL_CHOICES).get(level),
            'score': correct,
            'total': total,
            'ratio': round(ratio * 100, 1),
            'category_scores': category_scores,
            'category_totals': category_totals,
        })

    @action(detail=False, methods=['get'], url_path='my-result')
    def my_result(self, request):
        """GET /api/learning/placement/my-result/ → 내 최신 진단 결과"""
        result = PlacementResult.objects.filter(student=request.user).first()
        if not result:
            return Response({'has_result': False})

        return Response({
            'has_result': True,
            'id': result.id,
            'level': result.level,
            'level_label': dict(PlacementResult.LEVEL_CHOICES).get(result.level),
            'score': result.score,
            'total': result.total_questions,
            'ratio': round((result.score / result.total_questions) * 100, 1) if result.total_questions > 0 else 0,
            'category_scores': result.category_scores,
            'created_at': result.created_at,
        })


class GoalViewSet(viewsets.ViewSet):
    """목표 설정 관련 API"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='careers')
    def list_careers(self, request):
        """GET /api/learning/goals/careers/ → 직무 목록 + 필요 역량"""
        careers = CareerGoal.objects.prefetch_related('required_skills').all()
        data = [
            {
                'id': c.id,
                'title': c.title,
                'icon': c.icon,
                'description': c.description,
                'estimated_weeks': c.estimated_weeks,
                'required_skills': [
                    {'id': s.id, 'name': s.name, 'category': s.get_category_display(), 'difficulty': s.difficulty_level}
                    for s in c.required_skills.all()
                ],
            }
            for c in careers
        ]
        return Response(data)

    @action(detail=False, methods=['post'], url_path='set')
    def set_goal(self, request):
        """
        POST /api/learning/goals/set/
        Body: { "career_goal_id": 1 } 또는 { "custom_goal": "직접 입력 텍스트" }
        """
        career_goal_id = request.data.get('career_goal_id')
        custom_goal = request.data.get('custom_goal', '')

        # 기존 목표 업데이트 (있으면)
        goal, created = StudentGoal.objects.update_or_create(
            student=request.user,
            defaults={
                'career_goal_id': career_goal_id,
                'custom_goal_text': custom_goal,
            }
        )

        # 목표 변경 시 갭 맵 재생성
        if career_goal_id:
            _rebuild_gap_map(request.user, career_goal_id)

        return Response({
            'id': goal.id,
            'career_goal_id': goal.career_goal_id,
            'custom_goal_text': goal.custom_goal_text,
            'created': created,
        })

    @action(detail=False, methods=['get'], url_path='my-goal')
    def my_goal(self, request):
        """GET /api/learning/goals/my-goal/ → 내 현재 목표"""
        goal = StudentGoal.objects.filter(student=request.user).first()
        if not goal:
            return Response({'has_goal': False})

        career = goal.career_goal
        return Response({
            'has_goal': True,
            'career_goal': {
                'id': career.id,
                'title': career.title,
                'icon': career.icon,
                'estimated_weeks': career.estimated_weeks,
            } if career else None,
            'custom_goal_text': goal.custom_goal_text,
        })


class GapMapViewSet(viewsets.ViewSet):
    """갭 맵 관련 API"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='my-map')
    def my_map(self, request):
        """GET /api/learning/gapmap/my-map/ → 내 갭 맵 전체"""
        skills = StudentSkill.objects.filter(student=request.user).select_related('skill')

        # 카테고리별 그룹핑
        categories = {}
        for ss in skills:
            cat = ss.skill.get_category_display()
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                'id': ss.id,
                'skill_id': ss.skill.id,
                'name': ss.skill.name,
                'difficulty': ss.skill.difficulty_level,
                'status': ss.status,
                'progress': ss.progress,
            })

        # 전체 통계
        total = skills.count()
        owned = skills.filter(status='OWNED').count()
        learning = skills.filter(status='LEARNING').count()
        gap = skills.filter(status='GAP').count()

        return Response({
            'categories': categories,
            'stats': {
                'total': total,
                'owned': owned,
                'learning': learning,
                'gap': gap,
                'completion_rate': round((owned / total) * 100, 1) if total > 0 else 0,
            }
        })


class ProfessorDiagnosticView(APIView):
    """교수자용: 전체 레벨 분포 + 취약 역량 분석"""
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        """GET /api/learning/professor/{lecture_id}/diagnostics/"""
        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)

        # 1. 레벨 분포
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # 해당 강좌 수강생의 최신 진단 결과
        results = PlacementResult.objects.filter(
            Q(lecture=lecture) | Q(lecture__isnull=True),
            student__in=lecture.students.all()
        ).order_by('student', '-created_at').distinct('student')

        level_dist = {1: 0, 2: 0, 3: 0}
        for r in results:
            level_dist[r.level] = level_dist.get(r.level, 0) + 1

        total_diagnosed = sum(level_dist.values())

        # 2. 취약 역량 TOP 5
        all_skills = StudentSkill.objects.filter(
            student__in=lecture.students.all(),
            status='GAP'
        ).values('skill__name', 'skill__category').annotate(
            gap_count=Count('id')
        ).order_by('-gap_count')[:5]

        enrolled_count = lecture.students.count()
        weak_skills = [
            {
                'skill_name': s['skill__name'],
                'category': s['skill__category'],
                'gap_count': s['gap_count'],
                'gap_rate': round((s['gap_count'] / enrolled_count) * 100, 1) if enrolled_count > 0 else 0,
            }
            for s in all_skills
        ]

        return Response({
            'enrolled_count': enrolled_count,
            'diagnosed_count': total_diagnosed,
            'level_distribution': {
                'level_1': level_dist[1],
                'level_2': level_dist[2],
                'level_3': level_dist[3],
            },
            'level_percentages': {
                'level_1': round((level_dist[1] / total_diagnosed) * 100, 1) if total_diagnosed > 0 else 0,
                'level_2': round((level_dist[2] / total_diagnosed) * 100, 1) if total_diagnosed > 0 else 0,
                'level_3': round((level_dist[3] / total_diagnosed) * 100, 1) if total_diagnosed > 0 else 0,
            },
            'weak_skills_top5': weak_skills,
        })


# ══════════════════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════════════════

def _initialize_gap_map(user, level):
    """진단 결과 기반으로 초기 갭 맵 생성"""
    all_skills = Skill.objects.all()
    for skill in all_skills:
        # 레벨에 따라 초기 상태 결정
        if skill.difficulty_level <= level:
            # 내 레벨 이하의 스킬은 일부 보유로 간주
            if skill.difficulty_level < level:
                st = 'OWNED'
                prog = 80 + (level - skill.difficulty_level) * 10  # 80~100%
            else:
                st = 'LEARNING'
                prog = 30 + level * 10  # 40~60%
        else:
            st = 'GAP'
            prog = 0

        StudentSkill.objects.update_or_create(
            student=user, skill=skill,
            defaults={'status': st, 'progress': min(prog, 100)}
        )


def _rebuild_gap_map(user, career_goal_id):
    """목표 변경 시 갭 맵 재구성 (목표 직무의 필요 역량 기반)"""
    try:
        career = CareerGoal.objects.get(id=career_goal_id)
        required_skill_ids = set(career.required_skills.values_list('id', flat=True))

        # 기존 보유 상태는 유지하되, 목표에 없는 스킬의 우선순위는 낮춤
        # (현재로서는 기존 상태 유지 — 향후 확장점)
    except CareerGoal.DoesNotExist:
        pass
