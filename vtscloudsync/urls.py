from django.contrib import admin
from django.urls import path, include
from storageapp.views import *
from cloudsync.views import *


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('cloudsync.urls')), 
    path('accounts/', include('accounts.urls')),
    path('user/', include('storageapp.urls')),
    
]