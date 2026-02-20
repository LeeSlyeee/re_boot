from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LearningSessionViewSet, EnrollLectureView, PublicLectureListView, MyLectureListView, ChecklistViewSet
from .views_assessment import AssessmentViewSet
from .professor_views import LectureViewSet
from .rag_views import RAGViewSet
from .live_views import LiveSessionViewSet, JoinLiveSessionView, LectureMaterialViewSet, LiveNoteView, NoteApproveView, NoteMaterialLinkView, AbsentNoteListView
from .placement_views import PlacementViewSet, GoalViewSet, GapMapViewSet, ProfessorDiagnosticView

router = DefaultRouter()
router.register(r'sessions', LearningSessionViewSet, basename='session')
router.register(r'assessment', AssessmentViewSet, basename='assessment')
router.register(r'lectures', LectureViewSet, basename='lecture')
router.register(r'rag', RAGViewSet, basename='rag')
router.register(r'checklist', ChecklistViewSet, basename='checklist')

# Phase 0: 라이브 세션 인프라
router.register(r'live', LiveSessionViewSet, basename='live-session')
router.register(r'materials', LectureMaterialViewSet, basename='material')

# Phase 1: 수준 진단 + 갭 맵
router.register(r'placement', PlacementViewSet, basename='placement')
router.register(r'goals', GoalViewSet, basename='goals')
router.register(r'gapmap', GapMapViewSet, basename='gapmap')

urlpatterns = [
    path('enroll/', EnrollLectureView.as_view(), name='enroll-lecture'),
    path('lectures/public/', PublicLectureListView.as_view(), name='public-lectures'),
    path('lectures/my/', MyLectureListView.as_view(), name='my-lectures'),
    # 라이브 세션 입장 (학생용)
    path('live/join/', JoinLiveSessionView.as_view(), name='live-join'),
    path('live/<int:pk>/note/', LiveNoteView.as_view(), name='live-note'),
    path('live/<int:pk>/note/approve/', NoteApproveView.as_view(), name='note-approve'),
    path('live/<int:pk>/note/materials/', NoteMaterialLinkView.as_view(), name='note-materials'),
    path('absent-notes/<int:lecture_id>/', AbsentNoteListView.as_view(), name='absent-notes'),
    # Phase 1: 교수자 진단 분석
    path('professor/<int:lecture_id>/diagnostics/', ProfessorDiagnosticView.as_view(), name='professor-diagnostics'),
    path('', include(router.urls)),
]
