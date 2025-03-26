from django import forms

class PostForm(forms.Form):
    """Form for creating a new post."""
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'class': 'compose-input',
                'placeholder': 'Share your thoughts...',
                'rows': '3',
            }
        ),
        required=True,
    )

    class Media:
        css = {
            'all': ('css/compose_form.css',)
        } 