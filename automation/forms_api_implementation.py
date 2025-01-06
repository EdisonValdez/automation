# forms.py
import logging
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from automation.services.ls_backend import LSBackendClient, LSBackendException
from .models import Country, CustomUser, Business, Destination, Feedback, ScrapingTask, UserRole, Category, Level
from django.contrib.auth import get_user_model
import json
from django.db import transaction
logger = logging.getLogger(__name__)

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'mobile']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            #'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

class CustomUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=UserRole.ROLE_CHOICES,
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})  
    )
    destinations = forms.ModelMultipleChoiceField(
        queryset=Destination.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('email', 'mobile', 'role', 'destinations')
        widgets = {
            'email': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            # 'role' and 'destinations' widgets are set in field definitions
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            existing_classes = self.fields[field].widget.attrs.get('class', '')
            self.fields[field].widget.attrs['class'] = f"{existing_classes} form-control".strip()

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            with transaction.atomic():
                user.save()
                role = self.cleaned_data.get('role')
                if role:
                    UserRole.objects.create(user=user, role=role) 
                destinations = self.cleaned_data.get('destinations')
                if destinations:
                    user.destinations.set(destinations)
        return user

class CustomUserChangeForm(UserChangeForm):
    role = forms.ChoiceField(
        choices=UserRole.ROLE_CHOICES,
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})  
    )
    
    destinations = forms.ModelMultipleChoiceField(
        queryset=Destination.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'mobile', 'role', 'destinations')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'password' in self.fields:
            del self.fields['password']
            
        # Make username and email read-only if this is an existing user
        if self.instance and self.instance.pk:
            self.fields['username'].widget.attrs['readonly'] = True
            self.fields['email'].widget.attrs['readonly'] = True
            
        for field in self.fields:
            existing_classes = self.fields[field].widget.attrs.get('class', '')
            self.fields[field].widget.attrs['class'] = f"{existing_classes} form-control".strip()
        
        if self.instance and self.instance.pk:
            try:
                user_role = self.instance.roles.first()
                if user_role:
                    self.fields['role'].initial = user_role.role
                self.fields['destinations'].initial = self.instance.destinations.all()
            except UserRole.DoesNotExist:
                logger.warning(f"No role found for user {self.instance.username}")

    def clean_username(self):
        # If this is an existing user, return the current username without validation
        if self.instance and self.instance.pk:
            return self.instance.username
        return self.cleaned_data['username']

    def clean_email(self):
        # If this is an existing user, return the current email without validation
        if self.instance and self.instance.pk:
            return self.instance.email
        return self.cleaned_data['email']

    def save(self, commit=True):
        try:
            with transaction.atomic():
                user = super().save(commit=False)
                if commit:
                    user.save()
                     
                    role = self.cleaned_data.get('role')
                    if role: 
                        UserRole.objects.filter(user=user).delete()
                        UserRole.objects.create(user=user, role=role)
 
                    destinations = self.cleaned_data.get('destinations')
                    if destinations is not None:
                        user.destinations.set(destinations)
                    
                    logger.info(f"Successfully updated user {user.username}")
                return user
        except Exception as e:
            logger.error(f"Error saving user {user.username}: {str(e)}")
            raise
 
class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['name', 'code', 'phone_code']
 
class DestinationForm(forms.ModelForm):
    class Meta:
        model = Destination
        fields = ['name', 'description', 'cp', 'province', 'slogan', 'latitude', 'longitude', 'country', 'ls_id', 'ambassador']

    def clean_country(self):
        country = self.cleaned_data.get('country')
        if not country:
            raise forms.ValidationError("Country is required.")
        return country
    
    def __init__(self, *args, **kwargs):
        super(DestinationForm, self).__init__(*args, **kwargs)
        self.fields['ambassador'].required = False  
 

class ScrapingTaskForm(forms.ModelForm):
    file = forms.FileField(
        required=False,
        help_text="Upload a file containing search queries (one per line)",
        widget=forms.FileInput(attrs={'class': 'btn text-primary border-primary d-flex align-items-center mr-5'})
    )

    level = forms.ChoiceField(
        choices=[],  # Will be populated from LS Backend
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        error_messages={'required': 'Please select a level.'}
    )

    main_category = forms.ChoiceField(
        choices=[],  # Will be populated based on selected level
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        error_messages={'required': 'Please select a main category.'}
    )

    subcategory = forms.ChoiceField(
        choices=[],  # Will be populated based on selected main category
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
    )

    country = forms.ChoiceField(
        choices=[],  # Will be populated from LS Backend
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        error_messages={'required': 'Please select a country.'}
    )

    destination = forms.ChoiceField(
        choices=[],  # Will be populated based on selected country
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        error_messages={'required': 'Please select a destination.'}
    )

    class Meta:
        model = ScrapingTask
        fields = ['project_title', 'level', 'main_category', 'subcategory', 
                 'country', 'destination', 'description', 'file']
        widgets = {
            'project_title': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ls_client = LSBackendClient()

        empty_choice = [('', '---------')]

        # Initialize levels from LS Backend
        try:
            levels = ls_client.get_levels()
            self.fields['level'].choices = empty_choice + [
                (level['id'], level['title']) for level in levels
            ]
        except LSBackendException as e:
            logger.error(f"Failed to fetch levels: {e}")
            self.fields['level'].choices = empty_choice

        # Initialize countries from LS Backend
        try:
            countries = ls_client.get_countries()
            self.fields['country'].choices = empty_choice + [
                (country['id'], country['name']) for country in countries
            ]
        except LSBackendException as e:
            logger.error(f"Failed to fetch countries: {e}")
            self.fields['country'].choices = empty_choice

        # Initialize other fields with empty choices
        self.fields['main_category'].choices = empty_choice
        self.fields['subcategory'].choices = empty_choice
        self.fields['destination'].choices = empty_choice

        # Handle main category population based on level
        if 'level' in self.data:
            try:
                level_id = self.data.get('level')
                categories = ls_client.get_categories(level_id=level_id)
                self.fields['main_category'].choices = [
                    (cat['id'], cat['title']) for cat in categories 
                    if not cat.get('parent_id')
                ]
            except (LSBackendException, ValueError) as e:
                logger.error(f"Failed to fetch categories: {e}")
                self.fields['main_category'].choices = []

        # Handle subcategory population based on main category
        if 'main_category' in self.data:
            try:
                main_category_id = self.data.get('main_category')
                categories = ls_client.get_categories(category_id=main_category_id)
                self.fields['subcategory'].choices = [
                    (cat['id'], cat['title']) for cat in categories
                ]
            except (LSBackendException, ValueError) as e:
                logger.error(f"Failed to fetch subcategories: {e}")
                self.fields['subcategory'].choices = []

        # Handle destination population based on country
        if 'country' in self.data:
            try:
                country_id = self.data.get('country')
                cities = ls_client.get_cities(country_id=country_id)
                self.fields['destination'].choices = [
                    (city['id'], city['name']) for city in cities
                ]
            except (LSBackendException, ValueError) as e:
                logger.error(f"Failed to fetch destinations: {e}")
                self.fields['destination'].choices = []

        # Populate fields if editing existing instance
        if self.instance.pk:
            if self.instance.level:
                try:
                    categories = ls_client.get_categories(level_id=self.instance.level)
                    self.fields['main_category'].choices = [
                        (cat['id'], cat['title']) for cat in categories 
                        if not cat.get('parent_id')
                    ]
                except LSBackendException as e:
                    logger.error(f"Failed to fetch categories for existing instance: {e}")

            if self.instance.main_category:
                try:
                    subcategories = ls_client.get_categories(category_id=self.instance.main_category)
                    self.fields['subcategory'].choices = [
                        (cat['id'], cat['title']) for cat in subcategories
                    ]
                except LSBackendException as e:
                    logger.error(f"Failed to fetch subcategories for existing instance: {e}")

            if self.instance.country:
                try:
                    cities = ls_client.get_cities(country_id=self.instance.country)
                    self.fields['destination'].choices = [
                        (city['id'], city['name']) for city in cities
                    ]
                except LSBackendException as e:
                    logger.error(f"Failed to fetch destinations for existing instance: {e}")

    def clean(self):
        cleaned_data = super().clean()
        level = cleaned_data.get('level')
        main_category = cleaned_data.get('main_category')
        subcategory = cleaned_data.get('subcategory')
        country = cleaned_data.get('country')
        destination = cleaned_data.get('destination')

        logger.debug(f"Cleaning form data: level={level}, main_category={main_category}, subcategory={subcategory}, country={country}, destination={destination}")

        ls_client = LSBackendClient()

        try:
            # Validate that main_category belongs to the selected level
            if main_category and level:
                categories = ls_client.get_categories(level_id=level)
                valid_categories = [str(cat['id']) for cat in categories if not cat.get('parent_id')]
                if main_category not in valid_categories:
                    self.add_error('main_category', 
                        'The selected category does not belong to the selected level.')

            # Validate that subcategory belongs to the selected main category
            if subcategory and main_category:
                subcategories = ls_client.get_categories(category_id=main_category)
                valid_subcategories = [str(cat['id']) for cat in subcategories]
                if subcategory not in valid_subcategories:
                    self.add_error('subcategory', 
                        'The selected subcategory does not belong to the selected main category.')

            # Validate that destination belongs to the selected country
            if destination and country:
                cities = ls_client.get_cities(country_id=country)
                valid_destinations = [str(city['id']) for city in cities]
                if destination not in valid_destinations:
                    self.add_error('destination', 
                        'The selected destination does not belong to the selected country.')

        except LSBackendException as e:
            logger.error(f"Error validating form data with LS Backend: {e}")
            raise forms.ValidationError(
                "Unable to validate form data. Please try again later."
            )

        return cleaned_data

    def clean_file(self):
        """
        Validate the uploaded file if provided.
        """
        file = self.cleaned_data.get('file')
        if file:
            # Validate file type
            if file.content_type not in ['text/plain']:
                raise forms.ValidationError("Only text files are allowed.")
            
            # Validate file size (optional, adjust size as needed)
            if file.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError("File size must be under 5MB.")
            
            # Validate file content (optional)
            try:
                content = file.read().decode('utf-8')
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                if not lines:
                    raise forms.ValidationError("File appears to be empty.")
                if len(lines) > 1000:  # Adjust limit as needed
                    raise forms.ValidationError("Too many queries in file. Maximum is 1000.")
                file.seek(0)  # Reset file pointer
            except UnicodeDecodeError:
                raise forms.ValidationError("File must be a valid text file with UTF-8 encoding.")
            
        return file

    def save(self, commit=True):
        """
        Save the form and create a new ScrapingTask instance.
        """
        instance = super().save(commit=False)
        
        # Set status to PENDING
        instance.status = 'PENDING'
        
        # Store LS Backend IDs
        instance.level_id = self.cleaned_data.get('level')
        instance.main_category_id = self.cleaned_data.get('main_category')
        instance.subcategory_id = self.cleaned_data.get('subcategory')
        instance.country_id = self.cleaned_data.get('country')
        instance.destination_id = self.cleaned_data.get('destination')
        
        # Get and store names/titles from LS Backend for reference
        try:
            ls_client = LSBackendClient()
            
            # Store level title
            levels = ls_client.get_levels()
            level_data = next((level for level in levels if str(level['id']) == instance.level_id), None)
            if level_data:
                instance.level_title = level_data['title']
            
            # Store category titles
            if instance.main_category_id:
                categories = ls_client.get_categories(level_id=instance.level_id)
                category_data = next((cat for cat in categories if str(cat['id']) == instance.main_category_id), None)
                if category_data:
                    instance.main_category_title = category_data['title']
            
            # Store country and destination names
            if instance.country_id:
                countries = ls_client.get_countries()
                country_data = next((country for country in countries if str(country['id']) == instance.country_id), None)
                if country_data:
                    instance.country_name = country_data['name']
            
            if instance.destination_id:
                cities = ls_client.get_cities(country_id=instance.country_id)
                city_data = next((city for city in cities if str(city['id']) == instance.destination_id), None)
                if city_data:
                    instance.destination_name = city_data['name']
                    
        except LSBackendException as e:
            logger.error(f"Error fetching additional data from LS Backend during save: {e}")
            # Continue with save even if additional data fetch fails
        
        if commit:
            instance.save()
            logger.info(f"Created new Gathering Project Task with id: {instance.id}")
            
            # Create associated task in task queue if needed
            try:
                # Implement your task creation logic here
                pass
            except Exception as e:
                logger.error(f"Error creating associated task: {e}")
                
        return instance

 
class CsvImportForm(forms.Form):
    csv_upload = forms.FileField(label='Select a CSV file')

class BusinessForm(forms.ModelForm):
    main_category = forms.MultipleChoiceField(
        choices=[],  # Populated dynamically in __init__
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )

    tailored_category = forms.MultipleChoiceField(
        choices=[],  # Populated dynamically in __init__
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )

    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    level_title = forms.CharField(
        label="Level Title",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'})
    )

    level_type = forms.CharField(
        label="Level Type",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'})
    )

    class Meta:
        model = Business
        fields = [
            'status', 'title', 'level_title', 'level_type', 'city',
            'price', 'phone', 'website', 'main_category',
            'tailored_category', 'categories', 'description', 'types',
            'description_esp', 'description_eng', 'description_fr', 'operating_hours',
            'category_name', 'service_options'
        ]
        widgets = {
            'service_options': forms.HiddenInput(),
            'operating_hours': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super(BusinessForm, self).__init__(*args, **kwargs)
        
        # Populate main_category choices
        main_categories = Category.objects.filter(parent__isnull=True)
        self.fields['main_category'].choices = [(cat.title, cat.title) for cat in main_categories]
        if self.instance and self.instance.main_category:
            self.fields['main_category'].initial = [cat.strip() for cat in self.instance.main_category.split(',')]
        else:
            self.fields['main_category'].initial = []

        # Populate tailored_category choices
        subcategories = Category.objects.filter(parent__isnull=False)
        self.fields['tailored_category'].choices = [(cat.title, cat.title) for cat in subcategories]
        if self.instance and self.instance.tailored_category:
            self.fields['tailored_category'].initial = [cat.strip() for cat in self.instance.tailored_category.split(',')]
        else:
            self.fields['tailored_category'].initial = []

        # Populate level_title and level_type if related task exists
        if self.instance and self.instance.task and self.instance.task.level:
            self.fields['level_title'].initial = self.instance.task.level.title
            self.fields['level_type'].initial = self.instance.task.level.site_types

        # Log initial data
        logger.debug(f"Initialized BusinessForm for Business ID: {self.instance.id if self.instance else 'New Business'}")
        logger.debug(f"Initial main_category: {self.fields['main_category'].initial}")
        logger.debug(f"Initial tailored_category: {self.fields['tailored_category'].initial}")

    def clean_main_category(self):
        data = self.cleaned_data.get('main_category', [])
        if not data and self.instance.main_category:
            # Preserve existing categories if none selected
            return self.instance.main_category
        return ', '.join(data) if isinstance(data, (list, tuple)) else data

    def clean_tailored_category(self):
        data = self.cleaned_data.get('tailored_category', [])
        if not data and self.instance.tailored_category:
            # Preserve existing categories if none selected
            return self.instance.tailored_category
        return ', '.join(data) if isinstance(data, (list, tuple)) else data

    def clean_operating_hours(self):
        """
        Pass through the operating hours without any validation or formatting
        """
        hours = self.cleaned_data.get('operating_hours')
        if not hours:
            logger.debug("No operating_hours provided.")
            return hours
        try:
            if isinstance(hours, str):
                hours = json.loads(hours)
            logger.debug(f"Cleaned operating_hours: {hours}")
            return hours
        except json.JSONDecodeError:
            logger.error("JSONDecodeError while cleaning operating_hours.")
            return hours
        except Exception as e:
            logger.error(f"Error in operating_hours: {str(e)}")
            return hours

    def save(self, commit=True):
        business = super(BusinessForm, self).save(commit=False)
        
        # Log before saving
        logger.debug(f"Saving Business ID: {business.id}")
        logger.debug(f"Before Save - main_category: {business.main_category}")
        logger.debug(f"Before Save - tailored_category: {business.tailored_category}")
        
        if commit:
            business.save()
            # Log after saving
            logger.debug(f"After Save - main_category: {business.main_category}")
            logger.debug(f"After Save - tailored_category: {business.tailored_category}")

        return business
    
           
FeedbackFormSet = forms.inlineformset_factory(
    Business,
    Feedback,
    fields=['content', 'status'],
    extra=1,
    can_delete=True,
    widgets={
        'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        'status': forms.Select(attrs={'class': 'form-control'}),
    }
)