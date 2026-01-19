from django.urls import path
from accounts.views import *


app_name = 'accounts'


urlpatterns = [
    path('SignUp/', signup_page, name='signup_page'),
    path('SignIn/', signin_page, name='signin_page'),
    path('logout/', user_logout, name='user_logout'),
    path("post-login/", post_login_redirect, name="post_login"),
]