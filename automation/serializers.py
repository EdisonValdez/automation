# automation/serializers.py
from rest_framework import serializers
from .models import Business

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'title', 'address', 'city', 'country', 'lat', 'long', 'ambassador']
        read_only_fields = ['ambassador']
