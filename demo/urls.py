from django.urls import path
from django.contrib import admin

from autofixer.views import active_transitions

urlpatterns = [
    path("admin/", admin.site.urls),
    path("autofixer/active/", active_transitions),
]
