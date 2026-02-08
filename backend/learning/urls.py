from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LearningSessionViewSet, EnrollLectureView, PublicLectureListView, MyLectureListView
from .views_assessment import AssessmentViewSet
from .professor_views import LectureViewSet

from .rag_views import RAGViewSet

router = DefaultRouter()
router.register(r'sessions', LearningSessionViewSet, basename='session')
router.register(r'assessment', AssessmentViewSet, basename='assessment')
router.register(r'lectures', LectureViewSet, basename='lecture')
router.register(r'rag', RAGViewSet, basename='rag')

urlpatterns = [
    path('enroll/', EnrollLectureView.as_view(), name='enroll-lecture'),
    path('lectures/public/', PublicLectureListView.as_view(), name='public-lectures'),
    path('lectures/my/', MyLectureListView.as_view(), name='my-lectures'),
    path('', include(router.urls)),
]
