#automation/api/views.py
from datetime import timedelta
from datetime import datetime
from math import ceil
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Prefetch
from django.utils import timezone  
from django.conf import settings
from django.db.models.functions import TruncDate
import logging 
from automation.api.permissions import IsAdminOrAmbassador, IsAdminUser
from automation.models import (Category, Country, CustomUser,Destination, ScrapingTask, Business, Image)
from automation.tasks import User
from .serializers import (AdminStatsSerializer, ProjectSerializer, TaskSerializer, BusinessSerializer,ImageSerializer)
from .permissions import ( IsAdminUser, IsAmbassadorUser, IsAdminOrAmbassador, HasDestinationPermission, IsAuthenticatedOrReadOnly)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .serializers import (DashboardStatsSerializer, TimelineDataSerializer, BusinessStatusSerializer, DashboardDataSerializer)
from automation.services.dashboard_service import DashboardService  
from django.core.serializers.json import DjangoJSONEncoder 
import json
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

#Businesses#Businesses#Businesses
class BusinessViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessSerializer
    #permission_classes = [IsAuthenticated]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """
        Filter businesses based on user role:
        - Superuser/Admin: All
        - Ambassador: Only in their destinations
        - Others: none
        """
        user = self.request.user
        if user.is_superuser or user.roles.filter(role='ADMIN').exists():
            return Business.objects.filter(is_deleted=False)
        elif user.roles.filter(role='AMBASSADOR').exists():
            return Business.objects.filter(
                form_destination_id__in=user.destinations.values_list('id', flat=True),
                is_deleted=False
            )
        else:
            return Business.objects.none()

    @action(detail=False, methods=['GET'])
    def advanced_filter(self, request):
        """
        GET /api/businesses/advanced_filter/?status=IN_PRODUCTION&destination_id=1&destination_id=5&task=146
        """
        try:
            queryset = self.get_queryset()

            # 1) Collect query params
            statuses = request.query_params.getlist('status')  # multiple 
            dest_ids = request.query_params.getlist('destination_id')  # multiple 
            category = request.query_params.get('category', '').strip()
            task_ids = request.query_params.getlist('task')  # e.g. ?task=146&task=200
            date_from = request.query_params.get('date_from', '')
            date_to = request.query_params.get('date_to', '')
            sort_by = request.query_params.get('sort_by', '-scraped_at')
            page = int(request.query_params.get('page', 1))
            limit = int(request.query_params.get('limit', 12))

            if page < 1: 
                page = 1
            if limit < 1: 
                limit = 12

            # 2) Search functionality
            search = request.query_params.get('search', '').strip()
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(destination__name__icontains=search) |
                    Q(country__icontains=search)
                )

            # 2a) statuses => filter(status__in=[...])
            if statuses:
                queryset = queryset.filter(status__in=statuses)

            # 2b) destinations => filter(destination_id__in=[...])
            if dest_ids:
                # convert to int
                try:
                    dest_ids = list(map(int, dest_ids))
                    queryset = queryset.filter(destination_id__in=dest_ids)
                except ValueError:
                    pass

            # 2c) category => filter(main_category__icontains=category) (or exact match if you prefer)
            if category:
                queryset = queryset.filter(main_category__icontains=category)

            # 2d) tasks => filter(task_id__in=[...]) if your Business has a foreign key "task"
            # or if it is "task__in", adapt
            if task_ids:
                try:
                    t_ids = list(map(int, task_ids))
                    queryset = queryset.filter(task_id__in=t_ids)
                except ValueError:
                    pass

            # 2e) Date range => if you store a date/time in `scraped_at`
            # or created_at if you have that field
            if date_from:
                try:
                    df = datetime.strptime(date_from, '%Y-%m-%d')
                    queryset = queryset.filter(scraped_at__date__gte=df.date())
                except:
                    pass
            if date_to:
                try:
                    dt = datetime.strptime(date_to, '%Y-%m-%d')
                    queryset = queryset.filter(scraped_at__date__lte=dt.date())
                except:
                    pass

            # 3) Sorting 
            # check if sort_by references real fields like: '-scraped_at', 'title', '-title', 'status' ...
            valid_sorts = ['scraped_at', '-scraped_at', 'title', '-title', 'status', '-status', 'rank', '-rank']
            if sort_by not in valid_sorts:
                sort_by = '-scraped_at'
            queryset = queryset.order_by(sort_by)

            # 4) Pagination
            total_count = queryset.count()
            total_pages = ceil(total_count / limit) if total_count else 1
            if page > total_pages:
                page = total_pages
            offset = (page - 1) * limit
            results = queryset[offset : offset + limit]

            # 5) Serialize
            serializer = self.get_serializer(results, many=True)
            data = serializer.data

            return Response({
                'status': 'success',
                'data': data,
                'total_count': total_count,
                'page': page,
                'total_pages': total_pages
            })

        except Exception as e:
            logger.error(f"Error in advanced_filter: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 
    @action(detail=False)
    def by_destination(self, request):
        """
        GET /api/businesses/by_destination/?destination_id=1&destination_id=5
        => returns businesses in any of those destinations
        """
        try:
            # 1) Collect all destination_id from query params
            # e.g. ?destination_id=1&destination_id=5 => getlist('destination_id') => ["1", "5"]
            destination_ids = request.query_params.getlist('destination_id')
            if not destination_ids:
                return Response(
                    {'error': 'Please provide one or more destination_id'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 2) Convert them to integers if needed
            # or keep them as strings if your DB key is string-based
            ids = []
            for d in destination_ids:
                try:
                    ids.append(int(d))
                except ValueError:
                    pass  # ignore invalid

            if not ids:
                return Response({'error': 'Invalid destination IDs'}, status=400)

            # 3) Filter using .filter(destination_id__in=ids)
            businesses = self.get_queryset().filter(destination_id__in=ids)

            # 4) Serialize
            serializer = self.get_serializer(businesses, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error fetching businesses by destination: {str(e)}")
            return Response(
                {'error': 'Failed to fetch businesses'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
 
    @action(detail=False)
    def by_status(self, request):
        """
        Get businesses grouped by status
        GET /api/businesses/by_status/?status={status}
        """
        try:
            status_filter = request.query_params.get('status')
            businesses = self.get_queryset()
            
            if status_filter:
                businesses = businesses.filter(status=status_filter)

            status_counts = businesses.values('status').annotate(
                count=Count('id')
            )
            return Response(status_counts)
        except Exception as e:
            logger.error(f"Error fetching businesses by status: {str(e)}")
            return Response(
                {'error': 'Failed to fetch business status counts'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_destroy(self, instance):
        """Soft delete implementation"""
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save()

    @action(detail=False, methods=['GET'])
    def analytics(self, request):
        """
        Get business analytics by category and destination
        GET /api/businesses/analytics/?destination_id=1,2&category=Food&status=IN_PRODUCTION
        """
        try:
            queryset = self.get_queryset()
            
            # Get filter parameters
            destination_ids = request.query_params.get('destination_id', '').split(',')
            category = request.query_params.get('category', '').strip()
            status_filter = request.query_params.get('status', '').strip()

            # Apply filters
            if destination_ids and destination_ids[0]:
                try:
                    ids = [int(id) for id in destination_ids if id.isdigit()]
                    if ids:
                        queryset = queryset.filter(destination_id__in=ids)
                except ValueError:
                    pass

            if category:
                queryset = queryset.filter(
                    Q(main_category__icontains=category) |
                    Q(tailored_category__icontains=category)
                )

            if status_filter:
                queryset = queryset.filter(status=status_filter)

            # Get category distribution
            category_stats = queryset.values('main_category').annotate(
                count=Count('id')
            ).order_by('-count')

            # Get destination distribution
            destination_stats = queryset.values(
                'destination__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')

            # Get status distribution
            status_stats = queryset.values('status').annotate(
                count=Count('id')
            ).order_by('-count')

            return Response({
                'status': 'success',
                'data': {
                    'categories': list(category_stats),
                    'destinations': list(destination_stats),
                    'statuses': list(status_stats),
                    'total_businesses': queryset.count()
                }
            })

        except Exception as e:
            logger.error(f"Error in analytics: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class BusinessFilterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # 1️⃣ Pagination Parameters
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 12))
            page = max(page, 1)
            limit = max(limit, 1)

            # 2️⃣ Collect Filter Parameters
            search = request.GET.get("search", "").strip()
            category_id = request.GET.get("category", "").strip()
            destination_id = request.GET.get("destination", "").strip()
            status_filter = request.GET.get("status", "").strip()
            date_from = request.GET.get("date_from", "").strip()
            date_to = request.GET.get("date_to", "").strip()
            sort_by = request.GET.get("sort_by", "-scraped_at")

            # 3️⃣ Base Queryset
            queryset = self.get_business_queryset(request.user)

            # 4️⃣ Apply Filters
            queryset = self.apply_filters(
                queryset,
                search=search,
                category_id=category_id,
                destination_id=destination_id,
                date_from=date_from,
                date_to=date_to,
                status_filter=status_filter,
            )

            # 5️⃣ Sorting
            sort_map = {
                "created_at": "scraped_at",
                "-created_at": "-scraped_at",
                "scraped_at": "scraped_at",
                "-scraped_at": "-scraped_at",
                "title": "title",
                "-title": "-title",
                "status": "status",
                "-status": "-status",
            }
            sort_by = sort_map.get(sort_by, "-scraped_at")
            queryset = queryset.order_by(sort_by)

            # 6️⃣ Pagination
            total_count = queryset.count()
            total_pages = ceil(total_count / limit) if total_count > 0 else 1
            page = min(page, total_pages)
            offset = (page - 1) * limit
            businesses = queryset[offset : offset + limit]

            # 7️⃣ Serialize Data (includes full business details)
            serialized_data = BusinessSerializer(businesses, many=True).data

            return Response(
                {
                    "status": "success",
                    "data": serialized_data,
                    "total_count": total_count,
                    "page": page,
                    "total_pages": total_pages,
                }
            )

        except Exception as e:
            logger.error(f"Error in BusinessFilterView: {str(e)}", exc_info=True)
            return Response({"status": "error", "message": str(e)}, status=500)

    def get_business_queryset(self, user):
        """Replicates logic from BusinessViewSet"""
        if user.is_superuser or user.roles.filter(role="ADMIN").exists():
            return Business.objects.filter(is_deleted=False)
        elif user.roles.filter(role="AMBASSADOR").exists():
            return Business.objects.filter(
                form_destination_id__in=user.destinations.values_list("id", flat=True),
                is_deleted=False,
            )
        else:
            return Business.objects.none()

    def apply_filters(self, queryset, search="", category_id="", destination_id="", date_from="", date_to="", status_filter=""):
        """Filters businesses based on search, category, destination, dates, and status"""

        # 🔍 Improved Search Query
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(description__icontains=search) |  # Search in descriptions
                Q(destination__name__icontains=search) |
                Q(country__icontains=search)
            )

        # 🔹 Filter by Category
        if category_id:
            queryset = queryset.filter(main_category=category_id)

        # 🔹 Filter by Destination
        if destination_id:
            queryset = queryset.filter(destination_id=destination_id)

        # 📅 Date Filtering
        if date_from:
            try:
                df = datetime.strptime(date_from, "%Y-%m-%d").date()
                queryset = queryset.filter(scraped_at__date__gte=df)
            except ValueError:
                pass

        if date_to:
            try:
                dt = datetime.strptime(date_to, "%Y-%m-%d").date()
                queryset = queryset.filter(scraped_at__date__lte=dt)
            except ValueError:
                pass

        # 🔄 Status Filtering
        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
            if statuses:
                queryset = queryset.filter(status__in=statuses)

        return queryset

class BusinessStatusView(APIView):
    permission_classes = [IsAdminOrAmbassador]

    def get(self, request):
        try:
            # Get business status counts
            status_counts = Business.objects.values('status').annotate(
                count=Count('id')
            ).exclude(status__isnull=True)  # Exclude null status

            # Convert to the format needed by Chart.js
            data = {
                'labels': [],
                'datasets': [{
                    'data': [],
                    'backgroundColor': []
                }]
            }

            # Color mapping for different statuses
            colors = {
                'PENDING': '#f6c23e',     # warning
                'IN_PROGRESS': '#36b9cc',  # info
                'COMPLETED': '#1cc88a',    # success
                'FAILED': '#e74a3b',       # danger
                'DISCARDED': '#858796'     # secondary
            }

            for status in status_counts:
                data['labels'].append(status['status'])
                data['datasets'][0]['data'].append(status['count'])
                data['datasets'][0]['backgroundColor'].append(
                    colors.get(status['status'], '#858796')
                )

            return Response(data)
        except Exception as e:
            logger.error(f"Error in BusinessStatusView: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to fetch business status data'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
 
class BusinessStatusStatsView(APIView):
    def get(self, request):
        try:
            stats = Business.objects.values('status').annotate(
                count=Count('id')
            ).order_by('status')
            
            status_data = {
                'pending': 0,
                'reviewed': 0,
                'in_production': 0,
                'discarded': 0
            }
            
            for item in stats:
                if item['status'] == 'PENDING':
                    status_data['pending'] = item['count']
                elif item['status'] == 'REVIEWED':
                    status_data['reviewed'] = item['count']
                elif item['status'] == 'IN_PRODUCTION':
                    status_data['in_production'] = item['count']
                elif item['status'] == 'DISCARDED':
                    status_data['discarded'] = item['count']
            
            return Response({
                'status': 'success',
                'data': status_data
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#Businesses#Businesses#Businesses


#Tasks#Tasks#Tasks#Tasks#Tasks
class TaskViewSet(viewsets.ModelViewSet):
    queryset = ScrapingTask.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.roles.filter(role='ADMIN').exists():
            return ScrapingTask.objects.all()
        elif user.roles.filter(role='AMBASSADOR').exists():
            ambassador_destinations = user.destinations.all()
            return ScrapingTask.objects.filter(
                businesses__form_destination_id__in=ambassador_destinations
            ).distinct()
        return ScrapingTask.objects.none()

    @action(detail=True, methods=['get'], url_path='detailed_view')
    def detailed_view(self, request, pk=None):
        try:
            user = request.user
            task = get_object_or_404(ScrapingTask, pk=pk)
            
            # Check permissions and get appropriate business queryset
            if user.is_superuser or user.roles.filter(role='ADMIN').exists():
                # Admins see all businesses
                businesses = Business.objects.filter(
                    task=task,
                    is_deleted=False
                ).prefetch_related('images')
            elif user.roles.filter(role='AMBASSADOR').exists():
                # Ambassadors see only their assigned destinations
                ambassador_destinations = user.destinations.all()
                businesses = Business.objects.filter(
                    task=task,
                    is_deleted=False,
                    form_destination_id__in=ambassador_destinations
                ).prefetch_related('images')
            else:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Calculate status counts for all statuses
            status_counts = {}
            total_businesses = businesses.count()
            for status_code, status_name in Business.STATUS_CHOICES:
                count = businesses.filter(status=status_code).count()
                status_counts[status_code] = {
                    'count': count,
                    'name': status_name,
                    'percentage': (count / total_businesses * 100) if total_businesses > 0 else 0
                }

            # Calculate empty descriptions (excluding discarded)
            empty_descriptions = businesses.exclude(
                status='DISCARDED'
            ).filter(
                Q(description__isnull=True) |
                Q(description='') |
                Q(description='None') |
                Q(description__exact='No description Available')
            ).count()

            # Get navigation tasks based on user role
            if user.is_superuser or user.roles.filter(role='ADMIN').exists():
                base_task_queryset = ScrapingTask.objects.all()
            else:
                ambassador_destinations = user.destinations.all()
                base_task_queryset = ScrapingTask.objects.filter(
                    businesses__form_destination_id__in=ambassador_destinations
                ).distinct()

            previous_task = base_task_queryset.filter(id__lt=task.id).order_by('-id').first()
            next_task = base_task_queryset.filter(id__gt=task.id).order_by('id').first()

            # Prepare response data
            response_data = {
                'task': TaskSerializer(task).data,
                'businesses': BusinessSerializer(businesses, many=True).data,
                'status_counts': status_counts,
                'total_businesses': total_businesses,
                'empty_descriptions': empty_descriptions,
                'navigation': {
                    'previous_task': TaskSerializer(previous_task).data if previous_task else None,
                    'next_task': TaskSerializer(next_task).data if next_task else None,
                },
                'status_choices': Business.STATUS_CHOICES,
                'user_permissions': {
                    'is_admin': user.is_superuser or user.roles.filter(role='ADMIN').exists(),
                    'is_ambassador': user.roles.filter(role='AMBASSADOR').exists(),
                    'can_edit': user.is_superuser or user.roles.filter(role__in=['ADMIN', 'AMBASSADOR']).exists(),
                    'can_delete': user.is_superuser or user.roles.filter(role='ADMIN').exists(),
                    'can_move_to_production': user.is_superuser or user.roles.filter(role='ADMIN').exists(),
                }
            }

            return Response(response_data)

        except Exception as e:
            logger.error(f"Error in detailed_view for task {pk}: {str(e)}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['GET'], url_path='list')
    def list_custom(self, request):
        tasks = self.queryset.order_by('-id')
        data = [{"id": t.id, "project_title": t.project_title} for t in tasks]
        return Response(data, status=200)
    
class TaskListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tasks = ScrapingTask.objects.order_by('-id')
            data = []
            for t in tasks:
                data.append({
                    "id": t.id,
                    "project_title": t.project_title or f"Task #{t.id}",
                })
            return Response(data, status=200)
        except Exception as e:
            logger.error(f"Error listing tasks: {str(e)}", exc_info=True)
            return Response([], status=500)
 
class RecentTasksView(APIView):
    permission_classes = [IsAdminOrAmbassador]

    def get(self, request):
        try:
            limit = int(request.GET.get('limit', 5))
            
            # Base queryset with optimized joins
            queryset = ScrapingTask.objects.select_related(
                'user', 'destination'
            ).prefetch_related(
                'businesses'
            )

            # Filter based on user role
            if not request.user.is_superuser and not request.user.roles.filter(role='ADMIN').exists():
                ambassador_destinations = request.user.destinations.all()
                queryset = queryset.filter(destination__in=ambassador_destinations)

            recent_tasks = queryset.order_by('-created_at')[:limit]

            data = []
            for task in recent_tasks:
                # Get user display name with fallback to username
                user_display_name = task.user.get_full_name() if task.user else None
                if not user_display_name and task.user:
                    user_display_name = task.user.username
                elif not user_display_name:
                    user_display_name = 'System'

                data.append({
                    'id': task.id,
                    'project_title': task.project_title,
                    'status': task.status,
                    'created_at': task.created_at.strftime('%Y-%m-%d %H:%M'),
                    'completed_at': task.completed_at.strftime('%Y-%m-%d %H:%M'),
                    'destination': {
                        'id': task.destination.id if task.destination else None,
                        'name': task.destination.name if task.destination else 'N/A'
                    },
                    'business_count': task.businesses.count(),
                    'user': {
                        'id': task.user.id if task.user else None,
                        'display_name': user_display_name,
                        'username': task.user.username if task.user else 'System'
                    }
                })

            return Response({
                'status': 'success',
                'data': data,
                'total_count': queryset.count()
            })
        except Exception as e:
            logger.error(f"Error in RecentTasksView: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': 'Failed to fetch recent tasks'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 
class TaskFilterOptionsView(APIView):
    """
    Endpoint to get all available filter options
    """
    permission_classes = [IsAdminOrAmbassador]

    def get(self, request):
        try:
            # For ambassadors, filter destinations
            if not request.user.is_superuser and not request.user.roles.filter(role='ADMIN').exists():
                ambassador_destinations = request.user.destinations.all()
                destinations = ambassador_destinations
                tasks = ScrapingTask.objects.filter(destination__in=ambassador_destinations)
            else:
                destinations = Destination.objects.all()
                tasks = ScrapingTask.objects.all()

            filter_options = {
                'users': User.objects.filter(
                    id__in=tasks.values_list('user', flat=True)
                ).values('id', 'username').distinct(),
                
                'categories': Category.objects.filter(
                    id__in=tasks.values_list('main_category', flat=True)
                ).values('id', 'title').distinct(),
                
                'destinations': destinations.values('id', 'name').distinct(),
                
                'countries': Country.objects.filter(
                    id__in=tasks.values_list('country', flat=True)
                ).values('id', 'name').distinct(),
                
                'statuses': tasks.values_list('status', flat=True).distinct(),
            }

            return Response({
                'status': 'success',
                'data': filter_options
            })
        except Exception as e:
            logger.error(f"Error in TaskFilterOptionsView: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 
class TaskFilterView(APIView):
    """
    Endpoint to filter tasks based on various criteria.
    Also supports pagination via ?page=1&limit=12 (both optional).
    """
    permission_classes = [IsAdminOrAmbassador]
    serializer_class = ProjectSerializer

    def get(self, request):
        try:
            # 1. Read pagination params (with defaults)
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 12))
            if page < 1:
                page = 1
            if limit < 1:
                limit = 12

            # 2. Collect filter parameters
            filters = {
                'search': request.GET.get('search', ''),
                'user_id': request.GET.get('user'),
                'category_id': request.GET.get('category'),
                'destination_id': request.GET.get('destination'),
                'country_id': request.GET.get('country'),
                'status': request.GET.get('status'),  # comma-separated
                'date_from': request.GET.get('date_from'),
                'date_to': request.GET.get('date_to'),
                'sort_by': request.GET.get('sort_by', '-created_at'),
            }

            # 3. Base queryset
            queryset = ScrapingTask.objects.select_related(
                'user', 'country', 'destination', 'main_category'
            ).prefetch_related('businesses')

            # Ambassador restrictions
            if not request.user.is_superuser and not request.user.roles.filter(role='ADMIN').exists():
                ambassador_destinations = request.user.destinations.all()
                queryset = queryset.filter(destination__in=ambassador_destinations)

            # 4. Apply filters (search, user, category, etc.)
            queryset = self.apply_filters(queryset, filters)

            # 5. Annotate with business_count
            queryset = queryset.annotate(business_count=Count('businesses', distinct=True))

            # 6. Count total after filtering
            total_count = queryset.count()

            # 7. Calculate total_pages
            total_pages = ceil(total_count / limit) if total_count > 0 else 1

            # Clamp page
            if page > total_pages and total_pages > 0:
                page = total_pages

            # 8. Offset and slice
            offset = (page - 1) * limit
            queryset = queryset[offset : offset + limit]

            # 9. Serialize
            serializer = self.serializer_class(queryset, many=True)

            # 10. Return response with pagination info
            return Response({
                'status': 'success',
                'data': serializer.data,
                'total_count': total_count,
                'page': page,
                'total_pages': total_pages,
                'limit': limit
            })

        except Exception as e:
            logger.error(f"Error in TaskFilterView: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def apply_filters(self, queryset, filters):
        """
        Applies the search, user, category, destination, 
        status, date range, and sort_by filters.
        """
        # Search
        if filters['search']:
            queryset = queryset.filter(
                Q(project_title__icontains=filters['search']) |
                Q(user__username__icontains=filters['search']) |
                Q(destination__name__icontains=filters['search']) |
                Q(country__name__icontains=filters['search'])
            )

        # User
        if filters['user_id']:
            queryset = queryset.filter(user_id=filters['user_id'])

        # Category
        if filters['category_id']:
            queryset = queryset.filter(main_category_id=filters['category_id'])

        # Destination
        if filters['destination_id']:
            queryset = queryset.filter(destination_id=filters['destination_id'])

        # Country
        if filters['country_id']:
            queryset = queryset.filter(country_id=filters['country_id'])

        # Multi-status (comma-separated)
        if filters['status']:
            statuses = [s.strip() for s in filters['status'].split(',') if s.strip()]
            if statuses:
                queryset = queryset.filter(status__in=statuses)

        # Date From
        if filters['date_from']:
            date_from = datetime.strptime(filters['date_from'], '%Y-%m-%d')
            queryset = queryset.filter(created_at__gte=date_from)
        
        # Date To
        if filters['date_to']:
            date_to = datetime.strptime(filters['date_to'], '%Y-%m-%d')
            queryset = queryset.filter(created_at__lte=date_to)

        # Sort by
        return queryset.order_by(filters['sort_by'])
   
class TaskTimelineView(APIView):
    def get(self, request):
        try: 
            end_date = request.query_params.get('end_date')
            start_date = request.query_params.get('start_date')

            if not end_date:
                end_date = timezone.now().date()
            else:
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()

            if not start_date:
                start_date = end_date - timedelta(days=90)
            else:
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()

            # Query tasks with date aggregation
            tasks_data = ScrapingTask.objects.filter(
                created_at__date__range=[start_date, end_date]
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                tasks_count=Count('id'),
                businesses_count=Count('businesses', distinct=True)
            ).order_by('date')

            # Convert queryset to list and format dates
            formatted_data = [{
                'date': item['date'].strftime('%Y-%m-%d'),
                'tasks_count': item['tasks_count'],
                'businesses_count': item['businesses_count']
            } for item in tasks_data]

            # Calculate totals
            total_tasks = sum(item['tasks_count'] for item in formatted_data)
            total_businesses = sum(item['businesses_count'] for item in formatted_data)

            response_data = {
                'status': 'success',
                'data': formatted_data,
                'totals': {
                    'total_tasks': total_tasks,
                    'total_businesses': total_businesses
                }
            }

            logger.debug(f"Timeline data response: {response_data}")  # Debug log
            return Response(response_data)

        except Exception as e:
            logger.error(f"Error in TaskTimelineView: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
#Tasks#Tasks#Tasks#Tasks#Tasks

class DashboardStatsView(APIView):
    def get(self, request):
        try:
            service = DashboardService()
            stats = service.get_dashboard_stats()
            serializer = DashboardStatsSerializer(stats)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TimelineDataView(APIView):
    def get(self, request):
        try:
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            service = DashboardService()
            timeline_data = service.get_timeline_data(start_date, end_date)
            serializer = TimelineDataSerializer(timeline_data)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DashboardDataView(APIView):
    def get(self, request):
        try:
            start_date = request.query_params.get(
                'start_date',
                (timezone.now() - timezone.timedelta(days=30)).strftime('%Y-%m-%d')
            )
            end_date = request.query_params.get(
                'end_date',
                timezone.now().strftime('%Y-%m-%d')
            )
            
            service = DashboardService()
            dashboard_data = service.get_dashboard_data(start_date, end_date)
            serializer = DashboardDataSerializer(dashboard_data)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserDataView(APIView):
    def get(self, request, user_id):
        try:
            service = DashboardService()
            user_data = service.get_user_data(user_id)
            return Response(user_data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CategoryStatsView(APIView):
    def get(self, request):
        try:
            categories = Business.objects.values(
                'main_category', 'tailored_category'
            ).annotate(
                count=Count('id')
            ).order_by('-count')
            
            category_data = {
                'main_categories': {},
                'tailored_categories': {}
            }
            
            for item in categories:
                if item['main_category']:
                    if item['main_category'] not in category_data['main_categories']:
                        category_data['main_categories'][item['main_category']] = 0
                    category_data['main_categories'][item['main_category']] += item['count']
                
                if item['tailored_category']:
                    if item['tailored_category'] not in category_data['tailored_categories']:
                        category_data['tailored_categories'][item['tailored_category']] = 0
                    category_data['tailored_categories'][item['tailored_category']] += item['count']
            
            return Response({
                'status': 'success',
                'data': category_data
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DashboardSummaryView(APIView):
    def get(self, request):
        try:
            # Get date range from request or default to last 90 days
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(
                days=int(request.GET.get('days', 90))
            )
            
            # Get timeline data
            timeline_data = self.get_timeline_data(start_date, end_date)
            
            # Get status counts
            status_counts = Business.objects.values('status').annotate(
                count=Count('id')
            )
            
            # Format status data
            status_data = {
                'pending': 0,
                'reviewed': 0,
                'in_production': 0,
                'discarded': 0
            }
            
            for item in status_counts:
                status = item['status'].lower()
                if status in status_data:
                    status_data[status] = item['count']
            
            # Get category distribution
            category_stats = Business.objects.values('main_category').annotate(
                count=Count('id')
            ).order_by('-count')
            
            response_data = {
                'timeline_data': timeline_data,
                'status_data': status_data,
                'category_stats': list(category_stats),
                'total_businesses': Business.objects.count(),
                'total_destinations': Destination.objects.count()
            }
            
            return Response({
                'status': 'success',
                'data': json.dumps(response_data, cls=DjangoJSONEncoder)
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_timeline_data(self, start_date, end_date):
        timeline_data = (
            ScrapingTask.objects.filter(
                created_at__date__range=[start_date, end_date]
            ).values('created_at__date').annotate(
                task_count=Count('id', distinct=True),
                business_count=Count('businesses', distinct=True)
            ).order_by('created_at__date')
        )
        
        return {
            'dates': [item['created_at__date'] for item in timeline_data],
            'tasks': [item['task_count'] for item in timeline_data],
            'businesses': [item['business_count'] for item in timeline_data]
        }

class RecentProjectsView(APIView):
    permission_classes = [IsAdminOrAmbassador]
    serializer_class = ProjectSerializer

    def get(self, request):
        try:
            limit = int(request.GET.get('limit', 5))
            
            # Base queryset
            queryset = ScrapingTask.objects.select_related(
                'user', 'country', 'destination'
            ).prefetch_related('businesses')

            # Filter based on user role
            if not request.user.is_superuser and not request.user.roles.filter(role='ADMIN').exists():
                # For ambassadors, filter by their destinations
                ambassador_destinations = request.user.destinations.all()
                queryset = queryset.filter(destination__in=ambassador_destinations)

            recent_projects = queryset.order_by('-created_at')[:limit]
            
            serializer = self.serializer_class(recent_projects, many=True)
            return Response({
                'status': 'success',
                'data': serializer.data
            })
        except Exception as e:
            logger.error(f"Error in RecentProjectsView: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminStatsView(APIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminStatsSerializer

    def get(self, request):
        try:
            # Get ambassador count
            ambassador_count = CustomUser.objects.filter(
                roles__role='AMBASSADOR'
            ).count()
            
            # Get business counts by status
            business_status_counts = Business.objects.values(
                'status'
            ).annotate(
                count=Count('id')
            )
            
            # Get destination counts
            destination_stats = Destination.objects.aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(is_active=True))
            )
            
            # Prepare response data
            admin_stats = {
                'total_users': CustomUser.objects.count(),
                'total_businesses': Business.objects.count(),
                'total_destinations': destination_stats['total'],
                'active_destinations': destination_stats['active'],
                'user_role_count': {
                    'admin': CustomUser.objects.filter(roles__role='ADMIN').count(),
                    'ambassador': ambassador_count,
                    'user': CustomUser.objects.filter(roles__role='USER').count()
                },
                'business_status': {
                    item['status']: item['count'] 
                    for item in business_status_counts
                },
                'ambassador_count': ambassador_count,
                'recent_activity': {
                    'new_users': CustomUser.objects.filter(
                        date_joined__gte=timezone.now() - timezone.timedelta(days=30)
                    ).count(),
                    'new_businesses': Business.objects.filter(
                        created_at__gte=timezone.now() - timezone.timedelta(days=30)
                    ).count()
                }
            }
            
            serializer = self.serializer_class(data=admin_stats)
            serializer.is_valid(raise_exception=True)
            
            return Response({
                'status': 'success',
                'data': serializer.validated_data
            })
        except Exception as e:
            logger.error(f"Error in AdminStatsView: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 
class AmbassadorDataView(APIView):
    permission_classes = [IsAdminOrAmbassador]
    
    def get(self, request):
        try:
            user = request.user
            
            # Initialize response data structure
            response_data = {
                'destinations': [],
                'task_summary': {},
                'business_stats': {},
                'recent_activity': [],
                'performance_metrics': {}
            }
            
            # Get ambassador's destinations
            if user.is_superuser or user.roles.filter(role='ADMIN').exists():
                destinations = Destination.objects.all()
            else:
                destinations = user.destinations.all()
            
            # Get tasks for these destinations
            tasks = ScrapingTask.objects.filter(
                destination__in=destinations
            ).select_related('destination')
            
            # Get businesses for these destinations
            businesses = Business.objects.filter(
                Q(form_destination_id__in=destinations) |
                Q(city__in=destinations.values_list('name', flat=True))
            )
            
            # Calculate task summary
            response_data['task_summary'] = {
                'total': tasks.count(),
                'completed': tasks.filter(status='COMPLETED').count(),
                'in_progress': tasks.filter(status='IN_PROGRESS').count(),
                'pending': tasks.filter(status='PENDING').count()
            }
            
            # Calculate business statistics
            response_data['business_stats'] = {
                'total': businesses.count(),
                'by_status': {
                    status: businesses.filter(status=status).count()
                    for status in ['PENDING', 'REVIEWED', 'IN_PRODUCTION', 'DISCARDED']
                },
                'by_category': businesses.values('main_category').annotate(
                    count=Count('id')
                ).order_by('-count')
            }
            
            # Get recent activity (last 7 days)
            seven_days_ago = timezone.now() - timezone.timedelta(days=7)
            recent_tasks = tasks.filter(
                created_at__gte=seven_days_ago
            ).order_by('-created_at')
            
            response_data['recent_activity'] = [{
                'id': task.id,
                'project_title': task.project_title,
                'status': task.status,
                'destination': task.destination.name if task.destination else None,
                'created_at': task.created_at,
                'business_count': task.businesses.count()
            } for task in recent_tasks[:10]]  # Limit to last 10 activities
            
            # Calculate performance metrics
            total_businesses = businesses.count()
            if total_businesses > 0:
                response_data['performance_metrics'] = {
                    'completion_rate': (
                        businesses.filter(status='IN_PRODUCTION').count() / total_businesses
                    ) * 100,
                    'review_rate': (
                        businesses.filter(status='REVIEWED').count() / total_businesses
                    ) * 100,
                    'discard_rate': (
                        businesses.filter(status='DISCARDED').count() / total_businesses
                    ) * 100
                }
            
            # Format destination data
            response_data['destinations'] = [{
                'id': dest.id,
                'name': dest.name,
                'country': dest.country.name if dest.country else None,
                'business_count': businesses.filter(
                    Q(form_destination_id=dest.id) |
                    Q(city=dest.name)
                ).count(),
                'task_count': tasks.filter(destination=dest).count()
            } for dest in destinations]
            
            return Response({
                'status': 'success',
                'data': response_data
            })
            
        except Exception as e:
            logger.error(f"Error in AmbassadorDataView: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': 'An error occurred while fetching ambassador data',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_queryset(self):
        """Helper method to get filtered queryset based on user role"""
        user = self.request.user
        
        if user.is_superuser or user.roles.filter(role='ADMIN').exists():
            return ScrapingTask.objects.all()
            
        ambassador_destinations = user.destinations.all()
        return ScrapingTask.objects.filter(
            destination__in=ambassador_destinations
        )

class DestinationListAPI(APIView):
    def get(self, request):
        try:
            qs = Destination.objects.all().order_by('name')
            data = [{"id": d.id, "name": d.name} for d in qs]
            return Response(data)
        except:
            return Response([], status=200)
