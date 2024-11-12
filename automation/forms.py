# forms.py
import logging
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Country, CustomUser, Business, Destination, ScrapingTask, UserRole, Category, Level
from django.contrib.auth import get_user_model

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
    role = forms.ChoiceField(choices=UserRole.ROLE_CHOICES, required=True)
    destinations = forms.ModelMultipleChoiceField(queryset=Destination.objects.all(), required=False)

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('email', 'mobile', 'role', 'destinations')
        widgets = {
            'email': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'select'}),
            'destinations': forms.Select(attrs={'class': 'select'})


        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            role = self.cleaned_data.get('role')
            destinations = self.cleaned_data.get('destinations')
            UserRole.objects.create(user=user, role=role)
            user.destinations.set(destinations)
        return user

class CustomUserChangeForm(UserChangeForm):
    role = forms.ChoiceField(choices=UserRole.ROLE_CHOICES, required=True)
    destinations = forms.ModelMultipleChoiceField(queryset=Destination.objects.all(), required=False)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'mobile', 'role', 'destinations')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        if self.instance:
            try:
                user_role = self.instance.roles.first()
                self.fields['role'].initial = user_role.role
                self.fields['destinations'].initial = self.instance.destinations.all()
            except UserRole.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            role = self.cleaned_data.get('role')
            destinations = self.cleaned_data.get('destinations')
            UserRole.objects.update_or_create(user=user, defaults={'role': role})
            user.destinations.set(destinations)
        return user
 
class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['name', 'code', 'phone_code']
 
class DestinationForm(forms.ModelForm):
    class Meta:
        model = Destination
        fields = ['name', 'description', 'cp', 'province', 'slogan', 'latitude', 'longitude', 'country', 'ambassador']

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
        help_text="Upload a file containing search queries (one per line)",
        widget=forms.FileInput(attrs={'class': 'btn btn-light  mr-5'})
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
        fields = ['project_title', 'level', 'main_category', 'subcategory', 'country', 'destination', 'description', 'file']
        widgets = {
             'project_title': forms.TextInput(attrs={'class': 'form-control', 'readonly': True, }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize main category queryset to top-level categories
        self.fields['main_category'].queryset = Category.objects.filter(parent__isnull=True)

        # If instance exists and has a level, filter main categories by level
        if self.instance.pk and self.instance.level:
            self.fields['main_category'].queryset = Category.objects.filter(level=self.instance.level, parent__isnull=True)

        # Handle main category-subcategory dependency in POST data
        if 'main_category' in self.data:
            try:
                main_category_id = int(self.data.get('main_category'))
                self.fields['subcategory'].queryset = Category.objects.filter(parent_id=main_category_id)
            except (ValueError, TypeError):
                pass  # Invalid input from the client; fallback to empty queryset

        # If editing an existing instance, populate subcategory queryset
        elif self.instance.pk and self.instance.main_category:
            self.fields['subcategory'].queryset = Category.objects.filter(parent=self.instance.main_category)

        # Handle country-destination dependency in POST data
        if 'country' in self.data:
            try:
                country_id = int(self.data.get('country'))
                self.fields['destination'].queryset = Destination.objects.filter(country_id=country_id)
            except (ValueError, TypeError):
                pass  # Invalid input from the client; fallback to empty queryset

        # If editing an existing instance with a country, populate destination queryset
        elif self.instance.pk and self.instance.country:
            self.fields['destination'].queryset = Destination.objects.filter(country=self.instance.country)


    def clean(self):
        cleaned_data = super().clean()
        level = cleaned_data.get('level')
        main_category = cleaned_data.get('main_category')
        subcategory = cleaned_data.get('subcategory')
        country = cleaned_data.get('country')
        destination = cleaned_data.get('destination')

        logger.debug(f"Cleaning form data: level={level}, main_category={main_category}, subcategory={subcategory}, country={country}, destination={destination}")

        # Validate that main_category belongs to the selected level
        if main_category and level and main_category.level != level:
            self.add_error('main_category', 'The selected category does not belong to the selected level.')

        # Validate that subcategory belongs to the selected main category
        if subcategory and main_category and subcategory.parent != main_category:
            self.add_error('subcategory', 'The selected subcategory does not belong to the selected main category.')

        # Validate that destination belongs to the selected country
        if destination and country and destination.country != country:
            self.add_error('destination', 'The selected destination does not belong to the selected country.')

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
            logger.info(f"Created new ScrapingTask with id: {instance.id}")
        return instance


class CsvImportForm(forms.Form):
    csv_upload = forms.FileField(label='Select a CSV file')
 
class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['status', 'city', 'price', 'description', 'description_esp', 'description_eng', 'operating_hours', 'category_name', 'service_options']
        widgets = {
            'service_options': forms.HiddenInput(),
            'operating_hours': forms.HiddenInput(),
        }