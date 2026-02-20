"""
Phase 2-3: AI 복습 루트 + 간격 반복 API Views
별도 APIView — urls.py에서 path 등록
"""
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    ReviewRoute, SpacedRepetitionItem, LiveSession,
    LiveQuizResponse, LiveSessionNote, LiveParticipant,
)


class MyReviewRoutesView(APIView):
    """GET /api/learning/review-routes/my/ — 내 복습 루트 목록"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        routes = ReviewRoute.objects.filter(
            student=request.user,
            status__in=['AUTO_APPROVED', 'APPROVED', 'MODIFIED'],
        ).select_related('live_session').order_by('-created_at')[:10]

        data = []
        for r in routes:
            completed_count = len(r.completed_items) if r.completed_items else 0
            total_count = len(r.items) if r.items else 0
            data.append({
                'id': r.id,
                'session_code': r.live_session.session_code,
                'session_title': r.live_session.title,
                'items': r.items,
                'completed_items': r.completed_items,
                'total_est_minutes': r.total_est_minutes,
                'progress': round(completed_count / total_count * 100) if total_count > 0 else 0,
                'status': r.status,
                'created_at': r.created_at,
            })
        return Response({'routes': data})


class CompleteReviewItemView(APIView):
    """POST /api/learning/review-routes/{id}/complete-item/ — 복습 항목 완료"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        route = get_object_or_404(ReviewRoute, id=pk, student=request.user)
        item_order = request.data.get('order')
        if item_order is None:
            return Response({'error': 'order는 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        completed = route.completed_items or []
        if item_order not in completed:
            completed.append(item_order)
            route.completed_items = completed
            route.save()

        return Response({
            'completed_items': route.completed_items,
            'progress': round(len(completed) / len(route.items) * 100) if route.items else 0,
        })


class PendingReviewRoutesView(APIView):
    """GET /api/learning/review-routes/pending/ — 교수자용 승인 대기 루트"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        routes = ReviewRoute.objects.filter(
            live_session__lecture__instructor=request.user,
            status='SUGGESTED',
        ).select_related('live_session', 'student').order_by('-created_at')

        data = [
            {
                'id': r.id,
                'student_name': r.student.username,
                'session_title': r.live_session.title,
                'items_count': len(r.items) if r.items else 0,
                'total_est_minutes': r.total_est_minutes,
                'created_at': r.created_at,
            }
            for r in routes
        ]
        return Response({'routes': data})


class ApproveReviewRouteView(APIView):
    """POST /api/learning/review-routes/{id}/approve/ — 복습 루트 승인"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        route = get_object_or_404(ReviewRoute, id=pk, live_session__lecture__instructor=request.user)
        route.status = 'APPROVED'
        route.save()
        return Response({'ok': True, 'status': 'APPROVED'})


class EditReviewRouteView(APIView):
    """PATCH /api/learning/review-routes/{id}/ — 복습 루트 수정"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        route = get_object_or_404(ReviewRoute, id=pk, live_session__lecture__instructor=request.user)
        items = request.data.get('items')
        if items:
            route.items = items
            route.total_est_minutes = sum(i.get('est_minutes', 0) for i in items)
        route.status = 'MODIFIED'
        route.save()
        return Response({'ok': True, 'status': 'MODIFIED'})


class SpacedRepetitionDueView(APIView):
    """GET /api/learning/spaced-repetition/due/ — 오늘 복습할 항목"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        items = SpacedRepetitionItem.objects.filter(student=request.user)

        due_items = []
        for item in items:
            schedule = item.schedule or []
            for entry in schedule:
                if entry.get('completed'):
                    continue
                due_at = entry.get('due_at', '')
                if due_at and due_at <= now.isoformat():
                    due_items.append({
                        'id': item.id,
                        'concept_name': item.concept_name,
                        'review_num': entry['review_num'],
                        'label': entry.get('label', ''),
                        'review_question': item.review_question,
                        'review_options': item.review_options,
                        'due_at': due_at,
                    })
                    break  # 가장 이른 미완료 주기만

        return Response({'due_items': due_items, 'total': len(due_items)})


class CompleteSpacedRepView(APIView):
    """POST /api/learning/spaced-repetition/{id}/complete/ — 복습 완료"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        item = get_object_or_404(SpacedRepetitionItem, id=pk, student=request.user)
        user_answer = request.data.get('answer', '')
        is_correct = user_answer.strip() == item.review_answer.strip()

        # 정답이면 현재 주기 완료 처리
        if is_correct:
            schedule = item.schedule or []
            for entry in schedule:
                if not entry.get('completed'):
                    entry['completed'] = True
                    item.current_review = entry['review_num']
                    break
            item.schedule = schedule
            item.save()

        return Response({
            'is_correct': is_correct,
            'correct_answer': item.review_answer,
            'current_review': item.current_review,
        })
