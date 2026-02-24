from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import *
import razorpay
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse

# Create your views here.


@login_required
def upgrade_page(request):
    
    subscription = UserSubscription.objects.select_related("plan").filter(user=request.user).first()
    
            
    if subscription:
        current_plan = subscription.plan
        if subscription and current_plan:        

            # 🔥 Fetch only higher plans
            # plans = Plan.objects.filter(
            #     order__gt=current_plan.order
            # ).order_by("order")

            # # 🧠 If no higher plans → block upgrade
            # can_upgrade = plans.exists()

            plans = Plan.objects.filter()

            can_upgrade = plans.exists()

            if can_upgrade:
                return render(request, "subscriptions/upgrade.html", {
                    "plans": plans,
                    "current_plan": current_plan,
                    "can_upgrade": can_upgrade,
                })
            elif request.user.is_superuser:
                return redirect('storageapp:admin_dashboard')
            else:
                return redirect('storageapp:dashboard')

    
    


client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


@login_required
@csrf_exempt
def create_order(request):
    if request.method == "POST":
        
        plan_id = request.POST.get("plan_id")
        if not plan_id:
            return JsonResponse({"error": "Plan ID missing"}, status=400)
    
        plan = Plan.objects.filter(id=plan_id).first()
        if not plan:
            return JsonResponse({"error": "Invalid plan"}, status=404)

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
    else:
        return JsonResponse({"error": "Invalid request"}, status=400)


@login_required
@csrf_exempt
def payment_success(request):
    if request.method == "POST":
    
        data = request.POST

        payment = Payment.objects.filter(
            razorpay_order_id=data.get("razorpay_order_id")
        ).first()

        if not payment:
            return JsonResponse({"success": False, "error": "Payment not found"}, status=404)
        
        # 🔐 VERIFY SIGNATURE
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": data.get("razorpay_order_id"),
                "razorpay_payment_id": data.get("razorpay_payment_id"),
                "razorpay_signature": data.get("razorpay_signature"),
            })
        except razorpay.errors.SignatureVerificationError:
            # ❌ Signature mismatch → mark failed
            payment.status = "failed"
            payment.save()

            return JsonResponse({
                "success": False,
                "error": "Signature verification failed"
            }, status=400)

        payment.razorpay_payment_id = data.get("razorpay_payment_id")
        payment.razorpay_signature = data.get("razorpay_signature")
        payment.status = "paid"
        payment.save()

        # ✅ UPDATE SUBSCRIPTION
        subscription = UserSubscription.objects.filter(
            user=payment.user
        ).first()
        if subscription:
            subscription.plan = payment.plan
            subscription.save()
            return JsonResponse({"success": True})
        else:
            return JsonResponse({
                "success": False,
                "error": "Subscription not found"
            }, status=400)
    else:
        return JsonResponse({"success": False}, status=400)



