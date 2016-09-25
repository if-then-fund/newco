from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
  url(r'^$', views.ContributionFormView.as_view()),
  url(r'^thank-you$', views.thank_you),
  url(r'^admin/', admin.site.urls),
]
