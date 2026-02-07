from rest_framework import serializers
from .models import Portfolio

class PortfolioSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    portfolio_type_display = serializers.CharField(source='get_portfolio_type_display', read_only=True)

    class Meta:
        model = Portfolio
        fields = ['id', 'student', 'portfolio_type', 'portfolio_type_display', 'title', 'content', 'created_at']
        read_only_fields = ['student', 'created_at', 'portfolio_type_display']
