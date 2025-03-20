from django.shortcuts import render

# Create your views here.


def landing(request):
    print("landing")
    return render(request, "landing.html", {})
