from django.contrib import admin
from .models import (
    Lecture, LearningSession, STTLog, SessionSummary, 
    DailyQuiz, QuizQuestion, QuizAttempt, VectorStore,
    LiveSession, LiveParticipant, LectureMaterial, LiveSTTLog, PulseCheck, PulseLog,
    LiveQuiz, LiveQuizResponse, LiveQuestion, LiveSessionNote,
    WeakZoneAlert, AdaptiveContent, ReviewRoute, SpacedRepetitionItem,
    FormativeAssessment, FormativeResponse,
    NoteViewLog, GroupMessage, SkillBlock,
    Skill, CareerGoal, PlacementQuestion, PlacementResult,
    StudentGoal, StudentSkill
)

@admin.register(Lecture)
class LectureAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'access_code', 'created_at')
    search_fields = ('title', 'instructor__username', 'access_code')

@admin.register(LearningSession)
class LearningSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'lecture', 'session_order', 'is_completed', 'start_time')
    list_filter = ('is_completed', 'session_date')
    search_fields = ('student__username', 'lecture__title')

@admin.register(STTLog)
class STTLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'sequence_order', 'text_chunk_preview')
    
    def text_chunk_preview(self, obj):
        return obj.text_chunk[:50] + "..." if len(obj.text_chunk) > 50 else obj.text_chunk

@admin.register(SessionSummary)
class SessionSummaryAdmin(admin.ModelAdmin):
    list_display = ('session', 'created_at')

@admin.register(VectorStore)
class VectorStoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_type', 'content_preview', 'created_at')
    search_fields = ('content',)
    
    def content_preview(self, obj):
        return obj.content[:100] + "..."


# ── Phase 0: 라이브 세션 인프라 ──

@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'session_code', 'status', 'lecture', 'instructor', 'created_at')
    list_filter = ('status',)
    search_fields = ('session_code', 'title', 'lecture__title')

@admin.register(LiveParticipant)
class LiveParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'live_session', 'is_active', 'joined_at')
    list_filter = ('is_active',)

@admin.register(LectureMaterial)
class LectureMaterialAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'file_type', 'lecture', 'uploaded_by', 'uploaded_at')
    list_filter = ('file_type',)

@admin.register(LiveSTTLog)
class LiveSTTLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'live_session', 'sequence_order', 'text_preview')

    def text_preview(self, obj):
        return obj.text_chunk[:50] + "..." if len(obj.text_chunk) > 50 else obj.text_chunk

@admin.register(PulseCheck)
class PulseCheckAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'live_session', 'pulse_type', 'created_at')
    list_filter = ('pulse_type',)

@admin.register(LiveQuiz)
class LiveQuizAdmin(admin.ModelAdmin):
    list_display = ('id', 'live_session', 'question_text_preview', 'is_ai_generated', 'is_active', 'triggered_at')
    list_filter = ('is_ai_generated', 'is_active')

    def question_text_preview(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text

@admin.register(LiveQuizResponse)
class LiveQuizResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'quiz', 'student', 'answer', 'is_correct', 'responded_at')
    list_filter = ('is_correct',)

@admin.register(LiveQuestion)
class LiveQuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'live_session', 'question_preview', 'upvotes', 'is_answered', 'created_at')
    list_filter = ('is_answered',)

    def question_preview(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text

@admin.register(LiveSessionNote)
class LiveSessionNoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'live_session', 'status', 'created_at')
    list_filter = ('status',)

@admin.register(PulseLog)
class PulseLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'live_session', 'pulse_type', 'created_at')
    list_filter = ('pulse_type',)

@admin.register(WeakZoneAlert)
class WeakZoneAlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'live_session', 'trigger_type', 'status', 'created_at')
    list_filter = ('trigger_type', 'status')

@admin.register(AdaptiveContent)
class AdaptiveContentAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_material', 'level', 'status', 'created_at')
    list_filter = ('level', 'status')

@admin.register(ReviewRoute)
class ReviewRouteAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'live_session', 'status', 'total_est_minutes', 'created_at')
    list_filter = ('status',)

@admin.register(SpacedRepetitionItem)
class SpacedRepetitionItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'concept_name', 'current_review', 'created_at')
    search_fields = ('concept_name', 'student__username')

@admin.register(FormativeAssessment)
class FormativeAssessmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'live_session', 'status', 'total_questions', 'created_at')
    list_filter = ('status',)

@admin.register(FormativeResponse)
class FormativeResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'assessment', 'score', 'total', 'sr_items_created', 'submitted_at')
    list_filter = ('sr_items_created',)

# Phase 1
@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'difficulty_level', 'order')
    list_filter = ('category', 'difficulty_level')

@admin.register(CareerGoal)
class CareerGoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon', 'estimated_weeks')
    filter_horizontal = ('required_skills',)

@admin.register(PlacementQuestion)
class PlacementQuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'question_text', 'category', 'difficulty')
    list_filter = ('category', 'difficulty')

@admin.register(PlacementResult)
class PlacementResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'level', 'score', 'total_questions', 'created_at')
    list_filter = ('level',)

@admin.register(StudentGoal)
class StudentGoalAdmin(admin.ModelAdmin):
    list_display = ('student', 'career_goal', 'created_at')

@admin.register(StudentSkill)
class StudentSkillAdmin(admin.ModelAdmin):
    list_display = ('student', 'skill', 'status', 'progress', 'updated_at')
    list_filter = ('status', 'skill__category')

@admin.register(NoteViewLog)
class NoteViewLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'note', 'viewed_at')

@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'lecture', 'sender', 'title', 'message_type', 'target_level', 'created_at')
    list_filter = ('message_type', 'target_level')

@admin.register(SkillBlock)
class SkillBlockAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'skill', 'lecture', 'level', 'total_score', 'is_earned', 'earned_at')
    list_filter = ('is_earned', 'level')
