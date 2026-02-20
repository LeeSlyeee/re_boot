from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LearningSessionViewSet, EnrollLectureView, PublicLectureListView, MyLectureListView, ChecklistViewSet
from .views_assessment import AssessmentViewSet
from .professor_views import LectureViewSet
from .rag_views import RAGViewSet
from .live_views import LiveSessionViewSet, JoinLiveSessionView, LectureMaterialViewSet, LiveNoteView, NoteApproveView, NoteMaterialLinkView, AbsentNoteListView
from .placement_views import PlacementViewSet, GoalViewSet, GapMapViewSet, ProfessorDiagnosticView
from .review_views import (
    MyReviewRoutesView, CompleteReviewItemView, PendingReviewRoutesView,
    ApproveReviewRouteView, EditReviewRouteView,
    SpacedRepetitionDueView, CompleteSpacedRepView,
)
from .formative_views import GenerateFormativeView, GetFormativeView, SubmitFormativeView
from .adaptive_views import GenerateAdaptiveView, ListAdaptiveView, ApproveAdaptiveView, MyContentView

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
    # Phase 2-3: 복습 루트 + 간격 반복
    path('review-routes/my/', MyReviewRoutesView.as_view(), name='my-review-routes'),
    path('review-routes/<int:pk>/complete-item/', CompleteReviewItemView.as_view(), name='complete-review-item'),
    path('review-routes/pending/', PendingReviewRoutesView.as_view(), name='pending-review-routes'),
    path('review-routes/<int:pk>/approve/', ApproveReviewRouteView.as_view(), name='approve-review-route'),
    path('review-routes/<int:pk>/', EditReviewRouteView.as_view(), name='edit-review-route'),
    path('spaced-repetition/due/', SpacedRepetitionDueView.as_view(), name='sr-due'),
    path('spaced-repetition/<int:pk>/complete/', CompleteSpacedRepView.as_view(), name='sr-complete'),
    # Phase 2-4: 형성평가
    path('formative/<int:session_id>/generate/', GenerateFormativeView.as_view(), name='formative-generate'),
    path('formative/<int:session_id>/', GetFormativeView.as_view(), name='formative-get'),
    path('formative/<int:fa_id>/submit/', SubmitFormativeView.as_view(), name='formative-submit'),
    # Phase 2-2: 적응형 콘텐츠
    path('materials/<int:pk>/generate-adaptive/', GenerateAdaptiveView.as_view(), name='generate-adaptive'),
    path('materials/<int:pk>/adaptive/', ListAdaptiveView.as_view(), name='list-adaptive'),
    path('adaptive/<int:pk>/approve/', ApproveAdaptiveView.as_view(), name='approve-adaptive'),
    path('live/<int:pk>/my-content/', MyContentView.as_view(), name='my-content'),
    path('', include(router.urls)),
]
