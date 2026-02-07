from django.contrib import admin
from .models import (
    Lecture, LearningSession, STTLog, SessionSummary, 
    DailyQuiz, QuizQuestion, QuizAttempt, VectorStore
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
