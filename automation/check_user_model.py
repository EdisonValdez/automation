from django.apps import apps
from django.conf import settings

def run_check():
    try:
        user_model = apps.get_model(settings.AUTH_USER_MODEL)
        print(f"User model found: {user_model}")
    except Exception as e:
        print(f"Error finding user model: {e}")

    try:
        automation_app = apps.get_app_config('automation')
        print(f"Automation app found: {automation_app}")
        print("Models in automation app:")
        for model in automation_app.get_models():
            print(model)
    except Exception as e:
        print(f"Error finding automation app: {e}")

if __name__ == "__main__":
    import django
    django.setup()
    run_check()
