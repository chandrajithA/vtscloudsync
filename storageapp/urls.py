from django.urls import path
from .views import *

app_name = 'storageapp'

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),   
    path("admin/dashboard/", admin_dashboard, name="admin_dashboard"),
    path('upload/', upload_page, name='upload_page'),
    path('myfiles/', myfiles, name='myfiles'),  
    path('shared/', shared_files, name='shared_files'),  
    path('trash/', trash, name='trash'),  
    path('settings/', settings_page, name='settings_page'), 

    path("upload/cancelled/", upload_cancelled, name="upload_cancelled"),

    path("file/<int:file_id>/trash/", move_to_trash, name="move_to_trash"), 
    path("file/<int:file_id>/share/", share_file_api, name="share_file"),
    path("file/<int:file_id>/download/", download_file, name="download_file"),
    
    path("shared/<int:shared_id>/remove/", remove_shared_file, name="remove_shared_file"),
    path("shared/<int:shared_id>/remove_own/", remove_shared_own_file, name="remove_shared_own_file"),

    path("check-username/", check_username, name="check_username"),
    path("update-username/", update_username, name="update_username"),
    
    path("trash/restore/<int:file_id>/", restore_file, name="restore_file"),
    path("trash/delete/<int:file_id>/", delete_file, name="delete_file"),
    path("trash/restore-all/", restore_all, name="restore_all"),
    path("trash/empty/", empty_trash, name="empty_trash"),
    
    path("admin/api/user-activity/", admin_user_activity_api, name="admin_user_activity_api"),
    path("admin/api/plan-distribution/", admin_plan_distribution_api, name="admin_plan_distribution_api"),
    path("admin/api/storage-growth/", admin_storage_growth_api, name="admin_storage_growth_api"),
]