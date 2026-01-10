from django.urls import path
from .views import *

app_name = 'storageapp'

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),   
    path('upload/', upload_page, name='upload_page'),
    path('share/', share_file, name='share_file'),  
    path('myfiles/', myfiles, name='myfiles'),  
    path("myfiles/search/", myfiles_search, name="myfiles_search"),
    path('trash/', trash, name='trash'),  
    path("file/<int:file_id>/trash/", move_to_trash, name="move_to_trash"), 
    path("trash/restore/<int:file_id>/", restore_file, name="restore_file"),
    path("trash/delete/<int:file_id>/", delete_file, name="delete_file"),
    path("trash/restore-all/", restore_all, name="restore_all"),
    path("trash/empty/", empty_trash, name="empty_trash"),
    path('settings/', settings, name='settings'), 
]