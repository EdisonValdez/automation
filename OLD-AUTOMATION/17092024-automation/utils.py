import secrets
import string

def generate_key(length=40):
    """
    Generate a secure random string of letters and digits
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
 

def is_admin(user):
    return user.is_authenticated and user.is_admin()

def is_ambassador(user):
    return user.is_authenticated and user.is_ambassador()
 

def generate_key(length=40):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
