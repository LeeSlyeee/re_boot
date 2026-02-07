from rest_framework import serializers
from .models import LearningSession, STTLog, SessionSummary, DailyQuiz, QuizQuestion, QuizAttempt, Lecture

class LectureSerializer(serializers.ModelSerializer):
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Lecture
        fields = ['id', 'title', 'instructor', 'access_code', 'student_count', 'created_at']
        read_only_fields = ['instructor', 'access_code', 'created_at']

    def get_student_count(self, obj):
        return obj.students.count()

class PublicLectureSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.username', read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    
    class Meta:
        model = Lecture
        fields = ['id', 'title', 'instructor_name', 'created_at', 'is_enrolled']

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.students.filter(id=request.user.id).exists()
        return False

class LearningSessionSerializer(serializers.ModelSerializer):
    latest_summary = serializers.SerializerMethodField()

    class Meta:
        model = LearningSession
        # Removed 'course' from fields
        fields = ['id', 'student', 'section', 'lecture', 'session_order', 'start_time', 'end_time', 'is_completed', 'youtube_url', 'latest_summary']
        read_only_fields = ['student', 'start_time', 'end_time', 'is_completed']
        
    def create(self, validated_data):
        # Allow creating session without course/section for now (Demo Mode)
        return super().create(validated_data)

    def get_latest_summary(self, obj):
        summary = obj.summaries.last() # related_name='summaries'
        return summary.content_text if summary else None

class STTLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = STTLog
        fields = ['session', 'sequence_order', 'text_chunk', 'created_at']

class SessionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionSummary
        fields = '__all__'

class QuizQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizQuestion
        fields = ['id', 'question_text', 'options'] # 정답(correct_answer)은 클라이언트에 노출하지 않음

class DailyQuizSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, read_only=True)
    
    class Meta:
        model = DailyQuiz
        fields = ['id', 'quiz_date', 'is_passed', 'total_score', 'questions']

class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = '__all__'
