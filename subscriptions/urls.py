from django.urls import path
from .views import *

app_name = 'subscriptions'

urlpatterns = [
    path("upgrade/", upgrade_page, name="upgrade_page"),
    path("upgrade_user/", upgrade, name="upgrade"),
    path("create-order/", create_order, name="create_order"),
    path("payment-success/", payment_success, name="payment_success"),

]