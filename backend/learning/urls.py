from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LearningSessionViewSet, EnrollLectureView, PublicLectureListView, MyLectureListView, ChecklistViewSet
from .views_assessment import AssessmentViewSet
from .professor_views import LectureViewSet
from .rag_views import RAGViewSet
from .live_views import LiveSessionViewSet, JoinLiveSessionView, LectureMaterialViewSet, LiveNoteView

router = DefaultRouter()
router.register(r'sessions', LearningSessionViewSet, basename='session')
router.register(r'assessment', AssessmentViewSet, basename='assessment')
router.register(r'lectures', LectureViewSet, basename='lecture')
router.register(r'rag', RAGViewSet, basename='rag')
router.register(r'checklist', ChecklistViewSet, basename='checklist')

# Phase 0: 라이브 세션 인프라
router.register(r'live', LiveSessionViewSet, basename='live-session')
router.register(r'materials', LectureMaterialViewSet, basename='material')

urlpatterns = [
    path('enroll/', EnrollLectureView.as_view(), name='enroll-lecture'),
    path('lectures/public/', PublicLectureListView.as_view(), name='public-lectures'),
    path('lectures/my/', MyLectureListView.as_view(), name='my-lectures'),
    # 라이브 세션 입장 (학생용)
    path('live/join/', JoinLiveSessionView.as_view(), name='live-join'),
    path('live/<int:pk>/note/', LiveNoteView.as_view(), name='live-note'),
    path('', include(router.urls)),
]
