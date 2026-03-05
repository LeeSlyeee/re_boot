"""
실라버스 + 학습 목표 CRUD API
- POST /learning/lectures/{lecture_id}/syllabus/       → 주차 생성
- GET  /learning/lectures/{lecture_id}/syllabus/        → 주차 목록 조회
- POST /learning/syllabus/{week_id}/objective/          → 목표 추가
- DELETE /learning/objectives/{obj_id}/                  → 목표 삭제
- PATCH /learning/objectives/{obj_id}/                   → 목표 수정
- PATCH /learning/syllabus/{week_id}/                    → 주차 수정
- POST /learning/syllabus/{week_id}/upload-file/         → 파일 업로드
- GET  /learning/syllabus/{week_id}/download-file/       → 파일 다운로드
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse
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
            file_url = request.build_absolute_uri(s.file.url) if s.file else None
            data.append({
                'id': s.id,
                'week_number': s.week_number,
                'title': s.title,
                'description': s.description,
                'file_url': file_url,
                'file_name': s.file.name.split('/')[-1] if s.file else None,
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
    DELETE /learning/objectives/{obj_id}/  → 목표 삭제
    PATCH  /learning/objectives/{obj_id}/  → 목표 수정 [3-3]
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, obj_id):
        try:
            obj = LearningObjective.objects.get(id=obj_id)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except LearningObjective.DoesNotExist:
            return Response({'error': '목표를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, obj_id):
        try:
            obj = LearningObjective.objects.get(id=obj_id)
        except LearningObjective.DoesNotExist:
            return Response({'error': '목표를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get('content', '').strip()
        if content:
            obj.content = content
        order = request.data.get('order')
        if order is not None:
            obj.order = order
        obj.save()
        return Response({'id': obj.id, 'content': obj.content, 'order': obj.order})


class SyllabusUpdateView(APIView):
    """
    PATCH /learning/syllabus/{week_id}/  → 주차 제목/설명 수정 [3-3]
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, week_id):
        try:
            syl = Syllabus.objects.get(id=week_id)
        except Syllabus.DoesNotExist:
            return Response({'error': '주차를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        title = request.data.get('title')
        description = request.data.get('description')
        if title is not None:
            syl.title = title
        if description is not None:
            syl.description = description
        syl.save()
        return Response({
            'id': syl.id,
            'week_number': syl.week_number,
            'title': syl.title,
            'description': syl.description,
        })


class SyllabusFileUploadView(APIView):
    """
    POST /learning/syllabus/{week_id}/upload-file/  → 파일 업로드 [3-2]
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, week_id):
        try:
            syl = Syllabus.objects.get(id=week_id)
        except Syllabus.DoesNotExist:
            return Response({'error': '주차를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': '파일을 선택해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        # 기존 파일 삭제
        if syl.file:
            syl.file.delete(save=False)

        syl.file = uploaded_file
        syl.save()

        file_url = request.build_absolute_uri(syl.file.url) if syl.file else None
        return Response({
            'id': syl.id,
            'file_url': file_url,
            'file_name': uploaded_file.name,
            'message': '파일이 업로드되었습니다.',
        })


class SyllabusFileDownloadView(APIView):
    """
    GET /learning/syllabus/{week_id}/download-file/  → 파일 다운로드 [3-2]
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, week_id):
        try:
            syl = Syllabus.objects.get(id=week_id)
        except Syllabus.DoesNotExist:
            return Response({'error': '주차를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        if not syl.file:
            return Response({'error': '첨부된 파일이 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        return FileResponse(
            syl.file.open('rb'),
            as_attachment=True,
            filename=syl.file.name.split('/')[-1]
        )
