# serializers.py
from rest_framework import serializers
from .models import Business

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'title', 'description', 'status', 'city', 'address', 'phone', 'url', 'latitude', 'longitude', 'created_at', 'updated_at']
