from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..forms import PostForm
from ..models import Post

@login_required
def home(request):
    """Home page view."""
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            content = form.cleaned_data['content']
            # Create a new post
            post = Post(
                user_profile=request.user.userprofile,
                content=content,
                experiment=request.user.userprofile.experiment,
            )
            post.save()
            return redirect('home')
    else:
        form = PostForm()

    return render(request, 'pages/home.html', {
        'form': form,
    }) 