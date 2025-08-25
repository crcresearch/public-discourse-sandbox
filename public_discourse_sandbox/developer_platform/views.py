from django.views import generic


class IndexView(generic.TemplateView):
    template_name = "dev_plat/index.html"
