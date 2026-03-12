from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LearningSessionViewSet, EnrollLectureView, PublicLectureListView, MyLectureListView, ChecklistViewSet
from .views_assessment import AssessmentViewSet
from .professor_views import LectureViewSet
from .rag_views import RAGViewSet
from .live_views import LiveSessionViewSet, JoinLiveSessionView, LectureMaterialViewSet, LiveNoteView, NoteApproveView, NoteMaterialLinkView, AbsentNoteListView, StudentSessionSummaryView, LectureQuizHistoryView
from .note_views import AbsentSelfTestView
from .placement_views import PlacementViewSet, GoalViewSet, GapMapViewSet, ProfessorDiagnosticView
from .review_views import (
    MyReviewRoutesView, CompleteReviewItemView, PendingReviewRoutesView,
    ApproveReviewRouteView, EditReviewRouteView,
    SpacedRepetitionDueView, CompleteSpacedRepView,
)
from .formative_views import GenerateFormativeView, GetFormativeView, SubmitFormativeView, MyPendingFormativeView
from .adaptive_views import GenerateAdaptiveView, ListAdaptiveView, ApproveAdaptiveView, MyContentView
from .analytics_views import (
    AnalyticsOverviewView, SendMessageView, WeakInsightsView,
    AISuggestionsView, SuggestionActionView, SendGroupMessageView,
    QualityReportView, ApplyRedistributionView, MyMessagesView,
)
from .skillblock_views import SyncSkillBlocksView, MySkillBlocksView, MockInterviewDataView, SkillBlockDetailView
from .certificate_views import CertificateDataView
from .chat_views import AIChatViewSet
from .curriculum_views import CurriculumViewSet
from .syllabus_views import SyllabusListCreateView, ObjectiveCreateView, ObjectiveDeleteView, SyllabusUpdateView, SyllabusFileUploadView, SyllabusFileDownloadView
from .manager_views import (
    ManagerDashboardView, ClassMonitorView, AtRiskStudentsView,
    StudentProgressVisualization, QuizAnalyticsVisualization,
    SkillHeatmapVisualization, EngagementVisualization,
)

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

# AI 튜터 챗봇 + 커리큘럼 리라우팅
router.register(r'chat/sessions', AIChatViewSet, basename='chat-session')
router.register(r'curriculum', CurriculumViewSet, basename='curriculum')

urlpatterns = [
    path('enroll/', EnrollLectureView.as_view(), name='enroll-lecture'),
    path('lectures/public/', PublicLectureListView.as_view(), name='public-lectures'),
    path('lectures/my/', MyLectureListView.as_view(), name='my-lectures'),
    # 강의 기반 퀴즈 누적 이력 (세션 상세 화면용)
    path('lectures/<int:lecture_id>/quiz-history/', LectureQuizHistoryView.as_view(), name='lecture-quiz-history'),
    # 라이브 세션 입장 (학생용)
    path('live/join/', JoinLiveSessionView.as_view(), name='live-join'),
    path('live/<int:pk>/note/', LiveNoteView.as_view(), name='live-note'),
    path('live/<int:pk>/note/approve/', NoteApproveView.as_view(), name='note-approve'),
    path('live/<int:pk>/note/materials/', NoteMaterialLinkView.as_view(), name='note-materials'),
    path('absent-notes/<int:lecture_id>/', AbsentNoteListView.as_view(), name='absent-notes'),
    # B2: 학생 개인 세션 요약
    path('live/<int:session_id>/my-summary/', StudentSessionSummaryView.as_view(), name='student-session-summary'),
    # C1: 결석생 셀프 테스트
    path('absent-notes/<int:note_id>/self-test/', AbsentSelfTestView.as_view(), name='absent-self-test'),
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
    path('formative/my-pending/', MyPendingFormativeView.as_view(), name='formative-my-pending'),
    # Syllabus + Objective CRUD
    path('lectures/<int:lecture_id>/syllabus/', SyllabusListCreateView.as_view(), name='syllabus-list-create'),
    path('syllabus/<int:week_id>/objective/', ObjectiveCreateView.as_view(), name='objective-create'),
    path('syllabus/<int:week_id>/', SyllabusUpdateView.as_view(), name='syllabus-update'),
    path('syllabus/<int:week_id>/upload-file/', SyllabusFileUploadView.as_view(), name='syllabus-upload-file'),
    path('syllabus/<int:week_id>/download-file/', SyllabusFileDownloadView.as_view(), name='syllabus-download-file'),
    path('objectives/<int:obj_id>/', ObjectiveDeleteView.as_view(), name='objective-delete'),
    # Phase 2-2: 적응형 콘텐츠
    path('materials/<int:pk>/generate-adaptive/', GenerateAdaptiveView.as_view(), name='generate-adaptive'),
    path('materials/<int:pk>/adaptive/', ListAdaptiveView.as_view(), name='list-adaptive'),
    path('adaptive/<int:pk>/approve/', ApproveAdaptiveView.as_view(), name='approve-adaptive'),
    path('live/<int:pk>/my-content/', MyContentView.as_view(), name='my-content'),
    # Phase 3: 교수자 대시보드 분석
    path('professor/<int:lecture_id>/analytics/overview/', AnalyticsOverviewView.as_view(), name='analytics-overview'),
    path('professor/<int:lecture_id>/analytics/weak-insights/', WeakInsightsView.as_view(), name='weak-insights'),
    path('professor/<int:lecture_id>/analytics/ai-suggestions/', AISuggestionsView.as_view(), name='ai-suggestions'),
    path('professor/<int:lecture_id>/analytics/quality-report/', QualityReportView.as_view(), name='quality-report'),
    path('professor/<int:lecture_id>/send-message/', SendMessageView.as_view(), name='send-message'),
    path('professor/<int:lecture_id>/send-group-message/', SendGroupMessageView.as_view(), name='send-group-message'),
    path('professor/<int:lecture_id>/apply-redistribution/', ApplyRedistributionView.as_view(), name='apply-redistribution'),
    path('messages/my/', MyMessagesView.as_view(), name='my-messages'),
    # 스킬블록 시스템
    path('skill-blocks/sync/<int:lecture_id>/', SyncSkillBlocksView.as_view(), name='sync-skill-blocks'),
    path('skill-blocks/my/', MySkillBlocksView.as_view(), name='my-skill-blocks'),
    path('skill-blocks/interview-data/', MockInterviewDataView.as_view(), name='interview-data'),
    path('skill-blocks/<int:block_id>/', SkillBlockDetailView.as_view(), name='skill-block-detail'),
    # 수료증
    path('certificate/<str:lecture_code>/', CertificateDataView.as_view(), name='certificate-data'),
    # 매니저 대시보드 및 클래스 모니터링
    path('manager/dashboard/', ManagerDashboardView.as_view(), name='manager-dashboard'),
    path('manager/class/<int:class_id>/', ClassMonitorView.as_view(), name='class-monitor'),
    path('manager/class/<int:class_id>/at-risk/', AtRiskStudentsView.as_view(), name='at-risk-students'),
    # 시각화 데이터 피딩 API
    path('visualization/student-progress/', StudentProgressVisualization.as_view(), name='viz-student-progress'),
    path('visualization/quiz-analytics/', QuizAnalyticsVisualization.as_view(), name='viz-quiz-analytics'),
    path('visualization/skill-heatmap/', SkillHeatmapVisualization.as_view(), name='viz-skill-heatmap'),
    path('visualization/engagement/', EngagementVisualization.as_view(), name='viz-engagement'),
    path('', include(router.urls)),
]
