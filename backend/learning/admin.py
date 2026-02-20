from django.contrib import admin
from .models import (
    Lecture, LearningSession, STTLog, SessionSummary, 
    DailyQuiz, QuizQuestion, QuizAttempt, VectorStore,
    LiveSession, LiveParticipant, LectureMaterial, LiveSTTLog, PulseCheck,
    LiveQuiz, LiveQuizResponse
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
