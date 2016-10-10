from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
  url(r'^$', views.ContributionFormView.as_view()),
  url(r'^test-error-email$', views.test_error_email),
  url(r'^admin/', admin.site.urls),
]
