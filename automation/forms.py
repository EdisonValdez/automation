# forms.py
import logging
from urllib.parse import urlparse
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
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
        widget=forms.FileInput(attrs={
            'class': 'btn text-primary border-primary d-flex align-items-center mr-5'
        })
    )

    level = forms.ModelChoiceField(
        queryset=Level.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select a level",
        error_messages={'required': 'Please select a level.'}
    )

    main_category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select a category",
        error_messages={'required': 'Please select a main category.'}
    )

    subcategory = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        empty_label="Select a subcategory (optional)"
    )

    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select a country",
        error_messages={'required': 'Please select a country.'}
    )

    destination = forms.ModelChoiceField(
        queryset=Destination.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select a destination",
        error_messages={'required': 'Please select a destination.'}
    )

    class Meta:
        model = ScrapingTask
        fields = ['project_title', 'level', 'main_category', 'subcategory', 'country', 
                 'destination', 'description', 'file']
        widgets = {
            'project_title': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',         
                'placeholder': 'Enter description or paste Google Maps URL (one url)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize main category queryset
        self.fields['main_category'].queryset = Category.objects.filter(parent__isnull=True)

        # Handle level-based main category filtering
        if self.instance.pk and self.instance.level:
            self.fields['main_category'].queryset = Category.objects.filter(
                level=self.instance.level,
                parent__isnull=True
            )

        # Handle main category-subcategory dependency
        if 'main_category' in self.data:
            try:
                main_category_id = int(self.data.get('main_category'))
                self.fields['subcategory'].queryset = Category.objects.filter(
                    parent_id=main_category_id
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.main_category:
            self.fields['subcategory'].queryset = Category.objects.filter(
                parent=self.instance.main_category
            )

        # Handle country-destination dependency
        if 'country' in self.data:
            try:
                country_id = int(self.data.get('country'))
                self.fields['destination'].queryset = Destination.objects.filter(
                    country_id=country_id
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.country:
            self.fields['destination'].queryset = Destination.objects.filter(
                country=self.instance.country
            )

    def clean(self):
        cleaned_data = super().clean()
        level = cleaned_data.get('level')
        main_category = cleaned_data.get('main_category')
        subcategory = cleaned_data.get('subcategory')
        country = cleaned_data.get('country')
        destination = cleaned_data.get('destination')
        description = cleaned_data.get('description', '').strip()
        file = cleaned_data.get('file')

        logger.debug(
            f"Cleaning form data: level={level}, main_category={main_category}, "
            f"subcategory={subcategory}, country={country}, destination={destination}"
        )

        # Validate the relationships between fields
        if main_category and level and main_category.level != level:
            self.add_error(
                'main_category',
                'The selected category does not belong to the selected level.'
            )

        if subcategory and main_category and subcategory.parent != main_category:
            self.add_error(
                'subcategory',
                'The selected subcategory does not belong to the selected main category.'
            )

        if destination and country and destination.country != country:
            self.add_error(
                'destination',
                'The selected destination does not belong to the selected country.'
            )

        # Validate URL format if description contains URLs
        if description and description.startswith(('http://', 'https://')):
            urls = [url.strip() for url in description.split('\n') if url.strip()]
            for url in urls:
                try:
                    parsed_url = urlparse(url)
                    if not all([parsed_url.scheme, parsed_url.netloc]):
                        self.add_error(
                            'description',
                            f'Invalid URL format: {url}'
                        )
                except Exception as e:
                    self.add_error(
                        'description',
                        f'Error parsing URL: {url}. Error: {str(e)}'
                    )

        # Validate that at least one input method is provided
        if not (file or description):
            self.add_error(
                None,
                'Please either upload a file, enter a description, or paste URL.'
            )

        return cleaned_data

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if file.content_type not in ['text/plain']:
                raise forms.ValidationError("Only text files are allowed.")
        return file

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.status = 'PENDING'
        
        if commit:
            instance.save()
            logger.info(f"Created new Gathering Project Task with id: {instance.id}")
        
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