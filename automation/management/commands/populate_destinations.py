from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from ...models import CustomUser, Business

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'role', 'destination']
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'destination')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)

class BusinessAdmin(admin.ModelAdmin):
    list_display = ['title', 'city', 'country', 'ambassador']
    list_filter = ['city', 'country', 'ambassador']

admin.site.register(Business, BusinessAdmin)
