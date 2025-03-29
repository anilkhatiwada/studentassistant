from django.contrib import admin
from django.urls import path
from user.urls import urlpatterns as urlpatterns
from django.urls import include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('user/', include('user.urls')),
]
