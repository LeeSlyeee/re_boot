from rest_framework import serializers
from .models import LearningSession, STTLog, SessionSummary, DailyQuiz, QuizQuestion, QuizAttempt, Lecture, Syllabus, LearningObjective, StudentChecklist

class LearningObjectiveSerializer(serializers.ModelSerializer):
    is_checked = serializers.SerializerMethodField()

    class Meta:
        model = LearningObjective
        fields = ['id', 'content', 'order', 'is_checked']

    def get_is_checked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Check if StudentChecklist entry exists and is_checked is True
            return StudentChecklist.objects.filter(student=request.user, objective=obj, is_checked=True).exists()
        return False

class SyllabusSerializer(serializers.ModelSerializer):
    objectives = LearningObjectiveSerializer(many=True, read_only=True)

    class Meta:
        model = Syllabus
        fields = ['id', 'week_number', 'title', 'description', 'objectives']

class LectureSerializer(serializers.ModelSerializer):
    student_count = serializers.SerializerMethodField()
    syllabi = SyllabusSerializer(many=True, read_only=True)

    class Meta:
        model = Lecture
        fields = ['id', 'title', 'instructor', 'access_code', 'student_count', 'created_at', 'syllabi', 'start_date', 'end_date']
        read_only_fields = ['instructor', 'access_code', 'created_at']

    def get_student_count(self, obj):
        return obj.students.count()

class PublicLectureSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.username', read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    attendance_rate = serializers.SerializerMethodField()
    attended_days = serializers.SerializerMethodField()
    total_class_days = serializers.SerializerMethodField()
    
    class Meta:
        model = Lecture
        fields = ['id', 'title', 'instructor_name', 'created_at', 'is_enrolled',
                  'start_date', 'end_date', 'attendance_rate', 'attended_days', 'total_class_days']

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.students.filter(id=request.user.id).exists()
        return False

    def _calc_attendance(self, obj):
        """해당 강의의 클래스별 출석 데이터를 계산 (캐시)"""
        cache_attr = f'_attendance_cache_{obj.id}'
        if hasattr(self, cache_attr):
            return getattr(self, cache_attr)

        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            result = (0, 0, 0)
            setattr(self, cache_attr, result)
            return result

        user = request.user
        # 이 강의에서 수업이 진행된 모든 날짜 (전체 학생 기준)
        all_dates = set(
            LearningSession.objects
            .filter(lecture=obj)
            .values_list('session_date', flat=True)
            .distinct()
        )
        total = len(all_dates)

        # 이 학생이 이 강의에서 출석한 날짜
        my_dates = set(
            LearningSession.objects
            .filter(lecture=obj, student=user)
            .values_list('session_date', flat=True)
            .distinct()
        )
        attended = len(my_dates & all_dates)
        rate = round((attended / total * 100), 1) if total > 0 else 0

        result = (rate, attended, total)
        setattr(self, cache_attr, result)
        return result

    def get_attendance_rate(self, obj):
        return self._calc_attendance(obj)[0]

    def get_attended_days(self, obj):
        return self._calc_attendance(obj)[1]

    def get_total_class_days(self, obj):
        return self._calc_attendance(obj)[2]

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
        fields = ['id', 'session', 'sequence_order', 'text_chunk', 'speaker', 'video_offset', 'created_at']

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


# ═══════════════════════════════════════════════
# AI 튜터 챗봇 Serializers
# ═══════════════════════════════════════════════
from .models import AIChatSession, AIChatMessage, Curriculum, CurriculumItem, ReroutingLog


class AIChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIChatMessage
        fields = ['id', 'sender', 'message', 'sources', 'created_at']


class AIChatSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = AIChatSession
        fields = ['id', 'lecture', 'title', 'is_active', 'start_time',
                  'updated_at', 'message_count', 'last_message']
        read_only_fields = ['start_time', 'updated_at']

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        last = obj.messages.last()
        return {
            'sender': last.sender,
            'message': last.message[:100],
            'created_at': last.created_at.isoformat(),
        } if last else None


class AIChatSessionDetailSerializer(serializers.ModelSerializer):
    messages = AIChatMessageSerializer(many=True, read_only=True)
    lecture_title = serializers.CharField(
        source='lecture.title', read_only=True, default='일반'
    )

    class Meta:
        model = AIChatSession
        fields = ['id', 'lecture', 'lecture_title', 'title', 'is_active',
                  'start_time', 'updated_at', 'messages']


# ═══════════════════════════════════════════════
# 커리큘럼 리라우팅 Serializers
# ═══════════════════════════════════════════════

class CurriculumItemSerializer(serializers.ModelSerializer):
    lecture_title = serializers.CharField(
        source='lecture.title', read_only=True, default=''
    )

    class Meta:
        model = CurriculumItem
        fields = ['id', 'lecture', 'lecture_title', 'title', 'item_type',
                  'order_index', 'is_completed', 'is_supplementary',
                  'completed_at', 'created_at']


class ReroutingLogSerializer(serializers.ModelSerializer):
    reason_display = serializers.CharField(
        source='get_reason_display', read_only=True
    )

    class Meta:
        model = ReroutingLog
        fields = ['id', 'reason', 'reason_display', 'reason_detail',
                  'old_path', 'new_path', 'items_added', 'items_removed',
                  'ai_recommendation', 'created_at']


class CurriculumSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()

    class Meta:
        model = Curriculum
        fields = ['id', 'title', 'course_name', 'status', 'start_date',
                  'target_date', 'progress_percent', 'created_at',
                  'updated_at', 'item_count', 'completed_count']
        read_only_fields = ['start_date', 'progress_percent', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_completed_count(self, obj):
        return obj.items.filter(is_completed=True).count()


class CurriculumDetailSerializer(serializers.ModelSerializer):
    items = CurriculumItemSerializer(many=True, read_only=True)
    rerouting_logs = ReroutingLogSerializer(many=True, read_only=True)

    class Meta:
        model = Curriculum
        fields = ['id', 'title', 'course_name', 'status', 'start_date',
                  'target_date', 'progress_percent', 'created_at',
                  'updated_at', 'items', 'rerouting_logs']
