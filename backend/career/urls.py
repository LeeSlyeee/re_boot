from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PortfolioViewSet
from .interview_views import InterviewViewSet

router = DefaultRouter()
router.register(r'portfolios', PortfolioViewSet, basename='portfolio')
router.register(r'interview', InterviewViewSet, basename='interview')

urlpatterns = [
    path('', include(router.urls)),
]
