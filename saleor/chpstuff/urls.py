from django.conf.urls import url
from django.views.generic import TemplateView


urlpatterns = [
    url(r'^aboutus/', TemplateView.as_view(template_name='chpstuff/about.html'), name='about')
]
