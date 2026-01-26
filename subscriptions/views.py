from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import *
import razorpay
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse
from .models import Plan, Payment
from django.urls import reverse

# Create your views here.


def upgrade(request):
    if request.user.is_authenticated:
        return redirect('subscriptions:upgrade_page')
    else: 
        next_url = reverse('subscriptions:upgrade_page')
        request.session['next_url'] = next_url
        return redirect('accounts:signin_page')


def upgrade_page(request):
    
    subscription = UserSubscription.objects.select_related("plan").get(user=request.user)
    current_plan = subscription.plan

    if current_plan.name.lower() == "free":
        plans = Plan.objects.exclude(name__iexact="free")
    elif current_plan.name.lower() == "pro":
        plans = Plan.objects.filter(name__iexact="business")
    else:
        plans = Plan.objects.none()

    return render(request, "subscriptions/upgrade.html", {
        "plans": plans,
        "current_plan": current_plan
    })


client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


@login_required
@csrf_exempt
def create_order(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    plan_id = request.POST.get("plan_id")
    plan = get_object_or_404(Plan, id=plan_id)

    amount_paise = int(plan.price * 100)

    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    # ✅ CREATE PAYMENT RECORD
    payment = Payment.objects.create(
        user=request.user,
        plan=plan,
        amount=plan.price,
        razorpay_order_id=order["id"],
        status="created"
    )

    return JsonResponse({
        "order_id": order["id"],
        "amount": amount_paise,
        "key": settings.RAZORPAY_KEY_ID,
        "plan": plan.name
    })



@csrf_exempt
def payment_success(request):
    if request.method != "POST":
        return JsonResponse({"success": False}, status=400)

    data = request.POST

    payment = get_object_or_404(
        Payment,
        razorpay_order_id=data.get("razorpay_order_id")
    )

    payment.razorpay_payment_id = data.get("razorpay_payment_id")
    payment.razorpay_signature = data.get("razorpay_signature")
    payment.status = "paid"
    payment.save()

    # ✅ UPDATE SUBSCRIPTION
    subscription = UserSubscription.objects.get(user=payment.user)
    subscription.plan = payment.plan
    subscription.save()

    return JsonResponse({"success": True})



