from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from automation.models import UserRole

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a new user with specified roles'

    def add_arguments(self, parser):
        parser.add_argument('mobile', type=str)
        parser.add_argument('username', type=str)
        parser.add_argument('email', type=str)
        parser.add_argument('password', type=str)
        parser.add_argument('roles', nargs='+', type=str)

    def handle(self, *args, **options):
        mobile = options['mobile']
        username = options['username']
        email = options['email']
        password = options['password']
        roles = options['roles']

        try:
            user = User.objects.create_user(
                mobile=mobile,
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created user: {user.username}'))

            for role in roles:
                UserRole.objects.create(user=user, role=role.upper())
                self.stdout.write(self.style.SUCCESS(f'Added role {role} to user {user.username}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating user: {str(e)}'))
#python manage.py create_user_with_roles "+1234567890" "carmen" "carmen@localsecrets.travel" "12345678" AMBASSADOR
#python manage.py create_user_with_roles "+1234567890" "EdisonValdez" "edisonvaldez@localsecrets.travel" "12345678" ADMIN
