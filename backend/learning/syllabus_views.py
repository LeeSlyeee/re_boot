"""
실라버스 + 학습 목표 CRUD API
- POST /learning/lectures/{lecture_id}/syllabus/       → 주차 생성
- GET  /learning/lectures/{lecture_id}/syllabus/        → 주차 목록 조회
- POST /learning/syllabus/{week_id}/objective/          → 목표 추가
- DELETE /learning/objective/{obj_id}/                   → 목표 삭제
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Syllabus, LearningObjective, Lecture


class SyllabusListCreateView(APIView):
    """
    GET  /learning/lectures/{lecture_id}/syllabus/  → 주차 목록 + 각 주차의 objectives
    POST /learning/lectures/{lecture_id}/syllabus/  → 새 주차 생성
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        syllabi = Syllabus.objects.filter(lecture_id=lecture_id).prefetch_related('objectives')
        data = []
        for s in syllabi:
            data.append({
                'id': s.id,
                'week_number': s.week_number,
                'title': s.title,
                'description': s.description,
                'objectives': [
                    {'id': o.id, 'content': o.content, 'order': o.order}
                    for o in s.objectives.all()
                ],
            })
        return Response(data)

    def post(self, request, lecture_id):
        try:
            lecture = Lecture.objects.get(id=lecture_id, instructor=request.user)
        except Lecture.DoesNotExist:
            return Response({'error': '강의를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        week_number = request.data.get('week_number')
        title = request.data.get('title', '')
        description = request.data.get('description', '')

        if not week_number:
            return Response({'error': 'week_number 필수'}, status=status.HTTP_400_BAD_REQUEST)

        syl, created = Syllabus.objects.get_or_create(
            lecture=lecture,
            week_number=week_number,
            defaults={'title': title, 'description': description}
        )
        if not created:
            syl.title = title or syl.title
            syl.description = description or syl.description
            syl.save()

        return Response({
            'id': syl.id,
            'week_number': syl.week_number,
            'title': syl.title,
            'description': syl.description,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ObjectiveCreateView(APIView):
    """
    POST /learning/syllabus/{week_id}/objective/  → 목표 추가
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, week_id):
        try:
            syl = Syllabus.objects.get(id=week_id)
        except Syllabus.DoesNotExist:
            return Response({'error': '주차를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get('content', '').strip()
        if not content:
            return Response({'error': 'content 필수'}, status=status.HTTP_400_BAD_REQUEST)

        max_order = syl.objectives.count()
        obj = LearningObjective.objects.create(
            syllabus=syl,
            content=content,
            order=max_order + 1,
        )
        return Response({
            'id': obj.id,
            'content': obj.content,
            'order': obj.order,
        }, status=status.HTTP_201_CREATED)


class ObjectiveDeleteView(APIView):
    """
    DELETE /learning/objective/{obj_id}/  → 목표 삭제
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, obj_id):
        try:
            obj = LearningObjective.objects.get(id=obj_id)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except LearningObjective.DoesNotExist:
            return Response({'error': '목표를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
