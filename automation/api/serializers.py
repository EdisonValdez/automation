from rest_framework import serializers
from automation.models import ScrapingTask, Business, Image, Destination, CustomUser

class DestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    destinations = DestinationSerializer(many=True, read_only=True)
    roles = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'destinations',
            'roles'
        ]
        read_only_fields = ['is_active', 'roles']

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = '__all__'

class BusinessSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True)

    main_category_list = serializers.ListField(
        child=serializers.CharField(), 
        #source='main_category_list',
        required=False
    )
    tailored_category_list = serializers.ListField(
        child=serializers.CharField(),
        #source='tailored_category_list',
        required=False
    )

    class Meta:
        model = Business
        fields = '__all__'
 
class DashboardStatsSerializer(serializers.Serializer):
    total_projects = serializers.IntegerField()
    total_businesses = serializers.IntegerField()
    status_counts = serializers.DictField()
    translated_count = serializers.IntegerField()
    categories = serializers.DictField()
    status_details = serializers.DictField()
    available_destinations = serializers.ListField()
 
class TimelineDataSerializer(serializers.Serializer):
    dates = serializers.ListField(child=serializers.DateField())
    tasks = serializers.ListField(child=serializers.IntegerField())
    businesses = serializers.ListField(child=serializers.IntegerField())
    total_tasks = serializers.IntegerField()
    total_businesses = serializers.IntegerField()

class BusinessStatusSerializer(serializers.Serializer):
    pending = serializers.IntegerField()
    reviewed = serializers.IntegerField()
    in_production = serializers.IntegerField()
    discarded = serializers.IntegerField()

class DashboardDataSerializer(serializers.Serializer):
    timeline_data = TimelineDataSerializer()
    business_status_data = BusinessStatusSerializer()
    additional_stats = serializers.DictField(required=False)
 
class DestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ['id', 'name', 'country']

class ProjectSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    destination = DestinationSerializer(read_only=True)
    business_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    completed_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = ScrapingTask
        fields = [
            'id', 'project_title', 'status', 'created_at', 'completed_at',
            'user', 'country', 'destination', 'business_count'
        ]

class TaskSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    destination = DestinationSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    completed_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ScrapingTask
        fields = [
            'id', 'project_title', 'status', 'created_at', 'completed_at',
            'user', 'destination', 'status_display'
        ]

class AdminStatsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_businesses = serializers.IntegerField()
    total_destinations = serializers.IntegerField()
    active_destinations = serializers.IntegerField()
    user_role_count = serializers.DictField()
    business_status = serializers.DictField()
    ambassador_count = serializers.IntegerField()
    recent_activity = serializers.DictField()
 
class AmbassadorDataSerializer(serializers.Serializer):
    destinations = serializers.ListField(child=serializers.DictField())
    task_summary = serializers.DictField()
    business_stats = serializers.DictField()
    recent_activity = serializers.ListField(child=serializers.DictField())
    performance_metrics = serializers.DictField()

    class Meta:
        fields = ['destinations', 'task_summary', 'business_stats', 
                 'recent_activity', 'performance_metrics']
