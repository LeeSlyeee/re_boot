"""
스킬블록 시스템 API
- 스킬블록 자동 생성/갱신
- 갭 맵 vs 스킬블록 비교
- 모의면접 연계 데이터
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg
from django.utils import timezone

from .models import (
    SkillBlock, Skill, StudentSkill, Lecture, PlacementResult,
    LiveSession, LiveQuizResponse, PulseLog, FormativeResponse,
    FormativeAssessment, StudentChecklist, LearningObjective,
)


LEVEL_MAP = {'BEGINNER': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}
LEVEL_EMOJIS = {1: '🌱', 2: '🌿', 3: '🌸'}
LEVEL_NAMES = {1: '씨앗', 2: '새싹', 3: '꽃'}
EARN_THRESHOLD = 60  # 종합 60점 이상이면 블록 획득


class SyncSkillBlocksView(APIView):
    """POST /api/learning/skill-blocks/sync/{lecture_id}/
    학습자의 스킬블록을 현재 데이터 기준으로 자동 생성/갱신
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id)
        student = request.user

        # 현재 레벨
        pr = PlacementResult.objects.filter(
            student=student, lecture=lecture
        ).order_by('-created_at').first()
        level = LEVEL_MAP.get(pr.level, 2) if pr else 2

        # 강의에 연결된 스킬 (CareerGoal → required_skills)
        from .models import CareerGoal, StudentGoal
        student_goal = StudentGoal.objects.filter(student=student).first()
        if student_goal and student_goal.career_goal:
            skills = student_goal.career_goal.required_skills.all()
        else:
            # 강의에 관련된 StudentSkill에서 역추적
            skills = Skill.objects.filter(
                student_records__student=student
            ).distinct()

        if not skills.exists():
            return Response({'message': '연결된 스킬이 없습니다.', 'blocks': []})

        ended_sessions = LiveSession.objects.filter(lecture=lecture, status='ENDED')
        blocks_data = []
        earned_count = 0

        for skill in skills:
            # 1. 체크포인트 통과율 (퀴즈 정답률)
            qr = LiveQuizResponse.objects.filter(
                student=student, quiz__live_session__in=ended_sessions
            )
            qt = qr.count()
            qc = qr.filter(is_correct=True).count()
            checkpoint = (qc / qt * 100) if qt > 0 else 0

            # 2. 형성평가 점수
            fa_resps = FormativeResponse.objects.filter(
                student=student, assessment__live_session__in=ended_sessions
            )
            fa_avg = 0
            if fa_resps.exists():
                agg = fa_resps.aggregate(avg=Avg('score'))
                fa_avg = agg['avg'] or 0

            # 3. 이해도 (펄스)
            pulses = PulseLog.objects.filter(
                student=student, live_session__in=ended_sessions
            )
            pt = pulses.count()
            pu = pulses.filter(pulse_type='UNDERSTAND').count()
            understand = (pu / pt * 100) if pt > 0 else 50

            # 종합 점수 (가중 평균: 체크포인트 40% + 형성평가 35% + 이해도 25%)
            total = checkpoint * 0.4 + fa_avg * 0.35 + understand * 0.25
            is_earned = total >= EARN_THRESHOLD

            block, _ = SkillBlock.objects.update_or_create(
                student=student, skill=skill, lecture=lecture,
                defaults={
                    'level': level,
                    'checkpoint_score': round(checkpoint, 1),
                    'formative_score': round(fa_avg, 1),
                    'understand_score': round(understand, 1),
                    'total_score': round(total, 1),
                    'is_earned': is_earned,
                    'earned_at': timezone.now() if is_earned else None,
                }
            )

            if is_earned:
                earned_count += 1
                # StudentSkill 연동 → OWNED
                StudentSkill.objects.update_or_create(
                    student=student, skill=skill,
                    defaults={'status': 'OWNED', 'progress': min(int(total), 100)}
                )

            blocks_data.append({
                'id': block.id,
                'skill_name': skill.name,
                'skill_category': skill.get_category_display(),
                'level': level,
                'emoji': LEVEL_EMOJIS[level],
                'level_name': LEVEL_NAMES[level],
                'checkpoint_score': round(checkpoint, 1),
                'formative_score': round(fa_avg, 1),
                'understand_score': round(understand, 1),
                'total_score': round(total, 1),
                'is_earned': is_earned,
            })

        return Response({
            'blocks': blocks_data,
            'total_skills': len(blocks_data),
            'earned_count': earned_count,
            'earn_rate': round(earned_count / len(blocks_data) * 100, 1) if blocks_data else 0,
            'level': level,
            'emoji': LEVEL_EMOJIS[level],
            'level_name': LEVEL_NAMES[level],
        })


class MySkillBlocksView(APIView):
    """GET /api/learning/skill-blocks/my/
    내 스킬블록 전체 조회 + 갭 맵 비교
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = request.user
        blocks = SkillBlock.objects.filter(student=student).select_related('skill', 'lecture')

        earned = blocks.filter(is_earned=True)
        not_earned = blocks.filter(is_earned=False)

        # 갭 맵 연동
        student_skills = StudentSkill.objects.filter(student=student).select_related('skill')
        gap_skills = student_skills.filter(status='GAP')
        owned_skills = student_skills.filter(status='OWNED')
        learning_skills = student_skills.filter(status='LEARNING')

        # 카테고리별 그룹핑
        categories = {}
        for block in blocks:
            cat = block.skill.get_category_display()
            if cat not in categories:
                categories[cat] = {'earned': [], 'remaining': []}

            b_data = {
                'id': block.id,
                'skill_name': block.skill.name,
                'level': block.level,
                'emoji': LEVEL_EMOJIS.get(block.level, '🌱'),
                'level_name': LEVEL_NAMES.get(block.level, '씨앗'),
                'total_score': block.total_score,
                'checkpoint_score': block.checkpoint_score,
                'formative_score': block.formative_score,
                'understand_score': block.understand_score,
                'is_earned': block.is_earned,
                'earned_at': block.earned_at,
            }
            if block.is_earned:
                categories[cat]['earned'].append(b_data)
            else:
                categories[cat]['remaining'].append(b_data)

        return Response({
            'categories': categories,
            'summary': {
                'total_blocks': blocks.count(),
                'earned_blocks': earned.count(),
                'remaining_blocks': not_earned.count(),
                'earn_rate': round(earned.count() / blocks.count() * 100, 1) if blocks.count() > 0 else 0,
            },
            'gap_map': {
                'owned': owned_skills.count(),
                'learning': learning_skills.count(),
                'gap': gap_skills.count(),
                'total': student_skills.count(),
            },
        })


class MockInterviewDataView(APIView):
    """GET /api/learning/skill-blocks/interview-data/
    모의면접 연계 — 스킬블록 기반 피드백 데이터
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = request.user
        blocks = SkillBlock.objects.filter(student=student)
        earned = blocks.filter(is_earned=True)
        remaining = blocks.filter(is_earned=False)

        # 현재 레벨
        pr = PlacementResult.objects.filter(student=student).order_by('-created_at').first()
        level = LEVEL_MAP.get(pr.level, 2) if pr else 2

        # 모의면접 멘트 생성
        remaining_count = remaining.count()
        earned_count = earned.count()

        if remaining_count > 0:
            top_remaining = remaining.order_by('-total_score')[:3]
            almost_there = [
                f"{LEVEL_EMOJIS.get(b.level, '🌱')} {b.skill.name} ({b.total_score:.0f}점)"
                for b in top_remaining
            ]
            interview_hint = (
                f"현재 스킬블록이 {remaining_count}개 더 있으면 "
                f"더 훌륭한 면접 점수를 받으실 수 있을 거에요! "
                f"특히 {', '.join(almost_there)}이(가) 거의 다 왔어요."
            )
        else:
            interview_hint = (
                f"축하합니다! 🎉 모든 스킬블록을 획득하셨어요. "
                f"총 {earned_count}개의 스킬블록으로 면접에서 자신감을 보여주세요!"
            )

        return Response({
            'level': level,
            'emoji': LEVEL_EMOJIS[level],
            'level_name': LEVEL_NAMES[level],
            'earned_count': earned_count,
            'remaining_count': remaining_count,
            'interview_hint': interview_hint,
            'earned_skills': [
                {'name': b.skill.name, 'emoji': LEVEL_EMOJIS.get(b.level, '🌱'), 'score': b.total_score}
                for b in earned.select_related('skill')
            ],
        })


class SkillBlockDetailView(APIView):
    """
    PATCH/DELETE /api/learning/skill-blocks/{block_id}/
    스킬블록 수정 및 삭제
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, block_id):
        try:
            block = SkillBlock.objects.get(id=block_id, student=request.user)
        except SkillBlock.DoesNotExist:
            return Response({'error': '스킬블록을 찾을 수 없습니다.'}, status=404)

        # 허용 필드만 수정 (Whitelist)
        title = request.data.get('title')
        level = request.data.get('level')
        is_earned = request.data.get('is_earned')

        if title is not None:
            block.title = title
        if level is not None and level in LEVEL_MAP.values():
            block.level = level
        if is_earned is not None:
            block.is_earned = is_earned
            if is_earned:
                block.earned_at = timezone.now()

        block.save()
        return Response({
            'id': block.id,
            'skill_name': block.skill.name,
            'level': block.level,
            'is_earned': block.is_earned,
            'message': '스킬블록이 수정되었습니다.',
        })

    def delete(self, request, block_id):
        try:
            block = SkillBlock.objects.get(id=block_id, student=request.user)
        except SkillBlock.DoesNotExist:
            return Response({'error': '스킬블록을 찾을 수 없습니다.'}, status=404)

        block.delete()
        return Response({'message': '스킬블록이 삭제되었습니다.'}, status=204)
