from django.shortcuts import redirect
from django.urls import reverse

class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.user.is_admin():
                if not request.path.startswith(reverse('admin:index')):
                    return redirect('admin:index')
            elif request.user.is_ambassador():
                if not request.path.startswith('/ambassador/'):
                    return redirect('ambassador_dashboard')  # Make sure this URL name exists
        return self.get_response(request)
