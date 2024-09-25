from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import handler404
from django.urls import path, include

import automation

urlpatterns = [
    path('admin', admin.site.urls),
    path('', include(automation.urls))
]
# Custom error handlers
handler404 = 'automation.views.custom_404_view'

# Static files handling
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)