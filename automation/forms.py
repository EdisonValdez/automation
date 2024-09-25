# forms.py
import logging
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, Business, Destination, ScrapingTask, UserRole, Category, Subcategory, Level



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

class DestinationForm(forms.ModelForm):
    class Meta:
        model = Destination
        fields = ['name', 'country']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

  
class ScrapingTaskForm(forms.ModelForm):
    file = forms.FileField(
        help_text="Upload a file containing search queries (one per line)",
        widget=forms.FileInput(attrs={'class': 'btn btn-light d-flex align-items-center mr-5', 'style':'display:contents'})
    )
    level = forms.ModelChoiceField(
        queryset=Level.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select a level"
    )
    main_category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select a category"
    )
    subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        empty_label="Select a subcategory (optional)"
    )

    class Meta:
        model = ScrapingTask
        fields = ['project_title', 'level', 'main_category', 'subcategory', 'description', 'file']
        widgets = { 
            'project_title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Always populate main_category queryset
        self.fields['main_category'].queryset = Category.objects.all()
        
        # If we have an instance and level is set, filter categories
        if self.instance.pk and self.instance.level:
            self.fields['main_category'].queryset = Category.objects.filter(level=self.instance.level)
        
        # If we have an instance and main_category is set, filter subcategories
        if self.instance.pk and self.instance.main_category:
            self.fields['subcategory'].queryset = Subcategory.objects.filter(category=self.instance.main_category)

    def clean(self):
        cleaned_data = super().clean()
        level = cleaned_data.get('level')
        main_category = cleaned_data.get('main_category')
        subcategory = cleaned_data.get('subcategory')

        logger.debug(f"Cleaning form data: level={level}, main_category={main_category}, subcategory={subcategory}")

        if main_category and level and main_category.level != level:
            self.add_error('main_category', 'The selected category does not belong to the selected level.')

        if subcategory and main_category and subcategory.category != main_category:
            self.add_error('subcategory', 'The selected subcategory does not belong to the selected main category.')

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

class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['address', 'city', 'state', 'phone', 'status']
        widgets = {
            #'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            #'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            #'website': forms.URLInput(attrs={'class': 'form-control'}),
            #'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }