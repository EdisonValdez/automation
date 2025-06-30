from django.apps import AppConfig

class AutomationConfig(AppConfig):
    name = 'automation'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        import automation.models 
        import automation.signals  
