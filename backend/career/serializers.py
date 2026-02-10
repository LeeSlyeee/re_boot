from rest_framework import serializers
from .models import Portfolio, MockInterview, InterviewExchange

class PortfolioSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    portfolio_type_display = serializers.CharField(source='get_portfolio_type_display', read_only=True)

    class Meta:
        model = Portfolio
        fields = ['id', 'student', 'portfolio_type', 'portfolio_type_display', 'title', 'content', 'created_at']
        read_only_fields = ['student', 'created_at', 'portfolio_type_display']

class InterviewExchangeSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%H:%M:%S", read_only=True)
    
    class Meta:
        model = InterviewExchange
        fields = ['id', 'question', 'answer', 'feedback', 'score', 'order', 'created_at']

class MockInterviewSerializer(serializers.ModelSerializer):
    persona_display = serializers.CharField(source='get_persona_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    portfolio_title = serializers.CharField(source='portfolio.title', read_only=True)
    exchanges = InterviewExchangeSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = MockInterview
        fields = ['id', 'student', 'portfolio', 'portfolio_title', 'persona', 'persona_display', 
                 'status', 'status_display', 'created_at', 'exchanges']
        read_only_fields = ['student', 'created_at', 'exchanges', 'persona_display', 'status_display']
