from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LearningSessionViewSet, EnrollLectureView, PublicLectureListView
from .views_assessment import AssessmentViewSet
from .professor_views import LectureViewSet

router = DefaultRouter()
router.register(r'sessions', LearningSessionViewSet, basename='session')
router.register(r'assessment', AssessmentViewSet, basename='assessment')
router.register(r'lectures', LectureViewSet, basename='lecture')

urlpatterns = [
    path('enroll/', EnrollLectureView.as_view(), name='enroll-lecture'),
    path('lectures/public/', PublicLectureListView.as_view(), name='public-lectures'),
    path('', include(router.urls)),
]
