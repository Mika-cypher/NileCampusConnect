# core/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Service, Order, Review, Category, Message


class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your Nile University email'
        })
    )
    first_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        })
    )
    last_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        })
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Choose a username'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter your password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm your password'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and not email.endswith('@nileuniversity.edu.ng'):
            raise forms.ValidationError('You must use a Nile University email address.')
        return email


# core/forms.py  ── replace the existing ServiceForm class ──

class ServiceForm(forms.ModelForm):
    """
    Used for both creating and editing services.
    Category is optional — blank choice is included so existing
    services with no category still display correctly in the form.
    """
    class Meta:
        model = Service
        fields = ('title', 'description', 'price', 'delivery_time', 'category', 'image')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter service title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe your service in detail',
                'rows': 5,
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter price in ₦',
                'step': '0.01',
                'min': '0',
            }),
            'delivery_time': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2 days, 1 week',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show a friendly blank option instead of "---------"
        self.fields['category'].empty_label = 'Uncategorised'
        self.fields['category'].required = False

class DeliveryForm(forms.ModelForm):
    """
    Used by the freelancer to submit completed work.
    Both fields are optional together — but the view enforces that at least
    one of file or notes must be provided, giving flexibility for
    text-only deliverables (e.g., a written essay pasted in notes).
    """
    class Meta:
        model = Order
        fields = ('delivery_file', 'delivery_notes')
        widgets = {
            'delivery_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
            'delivery_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': (
                    'Describe what you have delivered — include any passwords, '
                    'links, or instructions the buyer needs.'
                ),
            }),
        }
        labels = {
            'delivery_file':  'Attach your work (optional if you include notes)',
            'delivery_notes': 'Delivery message',
        }

    def clean(self):
        cleaned_data = super().clean()
        delivery_file  = cleaned_data.get('delivery_file')
        delivery_notes = cleaned_data.get('delivery_notes', '').strip()

        if not delivery_file and not delivery_notes:
            raise forms.ValidationError(
                'Please attach a file, write a delivery message, or both. '
                'You cannot submit an empty delivery.'
            )
        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    """
    Lets a user update the fields they own: name, bio, avatar.
    Email and username are intentionally excluded — changing those
    requires separate verification flows we haven't built yet.
    """
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'bio', 'profile_picture')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your first name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your last name',
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': (
                    'Tell other students what you do — your skills, '
                    'experience, and what makes you great to work with.'
                ),
            }),
            'profile_picture': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
        }
        labels = {
            'profile_picture': 'Profile picture',
        }


class ReviewForm(forms.ModelForm):
    """
    Submitted by the buyer after accepting a delivery.
    Rating is rendered as large clickable stars via CSS in the template.
    """
    rating = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'star-radio'}),
        label='Your rating',
    )

    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': (
                    'Describe your experience — quality of work, '
                    'communication, and whether you would recommend them.'
                ),
            }),
        }
        labels = {
            'comment': 'Written feedback (optional)',
        }
class MessageForm(forms.ModelForm):
    """
    Single-field form for sending a message on an order thread.
    Rendered without a label — the placeholder carries enough context.
    """
    class Meta:
        model = Message
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={
                'class':       'form-control',
                'rows':        2,
                'placeholder': 'Type a message… (Shift+Enter for new line)',
            }),
        }
        labels = {
            'text': '',   # suppress the label — the UI makes context obvious
        }