from django import forms

class PostForm(forms.Form):
    """Form for creating a new post."""
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'class': 'compose-input',
                'name': 'post_content',
                'placeholder': 'Share your thoughts...',
                'maxlength': '500',
                'required': True,
                'rows': '3',
            }
        ),
        required=True,
    )

    class Media:
        css = {
            'all': ('css/main_dps.css',)
        } 