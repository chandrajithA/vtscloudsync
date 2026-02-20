from django.shortcuts import render, redirect
from .models import *
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
import re
from subscriptions.models import *

def signin_page(request):
    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect('storageapp:dashboard')
        else: 
            next_url = request.GET.get('next', '') or request.session.pop('next_url', '')
            prefill = request.session.pop('loginprefill', None)
            context = {
                            'next_url': next_url,
                            'prefill':prefill,
            }
            return render(request, 'accounts/signin_page.html', context)

    
    elif request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')
        remember_me = request.POST.get("remember_me")
        next_url = request.POST.get('next')

        user = User.objects.filter(username=username).first()
            
        if not user:
            request.session['next_url'] = next_url
            prefill = {
                'username': username,
                'password': "",
                'role':role,
            }
            request.session['loginprefill'] = prefill
            messages.error(request, "Invalid Username.")
            return redirect('accounts:signin_page')
        
        # 🔐 Role verification
        if role == "admin" and not user.is_superuser:
            request.session['next_url'] = next_url
            prefill = {
                'username': username,
                'password': password,
                'role':role,
            }
            request.session['loginprefill'] = prefill
            messages.error(request, "Admin access denied.")
            return redirect('accounts:signin_page')

        if role == "user" and user.is_superuser:
            request.session['next_url'] = next_url
            prefill = {
                'username': username,
                'password': password,
                'role':role,
            }
            request.session['loginprefill'] = prefill
            messages.error(request, "Please login as Admin.")
            return redirect('accounts:signin_page')

        # Check password
        elif not user.check_password(password):
            request.session['next_url'] = next_url
            prefill = {
                'username': username,
                'password': password,
                'role':role,
            }
            request.session['loginprefill'] = prefill
            messages.error(request, "Invalid Password.")
            return redirect('accounts:signin_page')

        # Check if user is active
        elif not user.is_active:
            request.session['next_url'] = next_url
            prefill = {
                'username': username,
                'password': "",
                'role':role,
            }
            request.session['loginprefill'] = prefill
            messages.error(request, "Account inactive. Contact Admin.")
            return redirect('accounts:signin_page')
        
        else:
            # Log in the user
            login(request, user, 'django.contrib.auth.backends.ModelBackend')
            UserLoginActivity.objects.create(user=user,ip_address=get_client_ip(request))
            if remember_me == "on":
                request.session.set_expiry(6 * 60 * 60)  
            else:
                request.session.set_expiry(0)
            if user.is_superuser:
                return redirect(next_url or 'storageapp:admin_dashboard')
            else:
                return redirect(next_url or 'storageapp:dashboard')
            
        



def signup_page(request):
    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect('storageapp:dashboard')
        
        else:
            prefill = request.session.pop('signupprefill', None)
            context = {
                'prefill':prefill,
            }

            return render(request,'accounts/signup_page.html', context)
        
    elif request.method == "POST":
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        userid = request.POST.get('userid')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        valid = True

        if not name.strip():
            messages.error(request, "Name cannot be empty or spaces only.")
            valid = False
        elif len(name) >= 50 :
            messages.error(request, "Name should contain less than 50 letters.")
            valid = False
        elif not re.fullmatch(r'[A-Za-z ]+', name):
            messages.error(request, "Name can only contain letters and spaces.")
            valid = False
        elif len(re.sub(r'[^A-Za-z]', '', name)) < 4:
            messages.error(request, "Name must contain at least 4 letters.")
            valid = False

        # 2. Phone number validation
        if not re.fullmatch(r'\d{10}', phone):
            messages.error(request, "Phone number must be exactly 10 digits.")
            valid = False
        elif User.objects.filter(phone=phone).exists():
            messages.error(request, "Phone number already registered.")
            valid = False

        # 3. Email validation
        if not re.fullmatch(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
            messages.error(request, "Email ID invalid")
            valid = False
        elif User.objects.filter(email=email).exists():
            messages.error(request, "Email ID already registered.")
            valid = False

        
        # 4. UserId validation
        if not userid.strip():
            messages.error(request, "User ID cannot be empty or spaces only.")
            valid = False
        elif not re.fullmatch(r'[A-Za-z0-9]+', userid):
            messages.error(request, "User ID can only contain letters and numbers (no spaces).")
            valid = False
        elif len(userid) > 32 :
            messages.error(request, "User ID should contain less than 32 letters.")
            valid = False
        elif len(userid) < 5 :
            messages.error(request, "User ID should contain atleast 8 letters.")
            valid = False

        elif User.objects.filter(username=userid).exists():
            messages.error(request, "User ID already registered.")
            valid = False


        # 5. Password validation
        if len(password) < 8:
            messages.error(request, "Password should be more than 8 characters.")
            valid = False
        elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            messages.error(request, "Password must include at least one special character.")
            valid = False
        elif not re.search(r'[A-Z]', password):
            messages.error(request, "Password must include at least one uppercase letter.")
            valid = False
        elif not re.search(r'[a-z]', password):
            messages.error(request, "Password must include at least one lowercase letter.")
            valid = False
        elif not re.search(r'\d', password):
            messages.error(request, "Password must include at least 1 number.")
            valid = False

        # 6. Confirm password match
        if password != confirm_password:
            messages.error(request, "Confirm Passwords not match with password.")
            valid = False

        if valid:
            # Create user
            user = User.objects.create_user(
                phone=phone,
                email=email,
                password=password,
                first_name=name,
                username=userid,
            )

            # 2️⃣ Attach FREE plan (already created by admin)
            try:
                free_plan = Plan.objects.get(name__iexact="free")
                UserSubscription.objects.create(
                    user=user,
                    plan=free_plan
                )
            except Plan.DoesNotExist:
                messages.error(
                    request,
                    "Free plan not configured. Please contact admin."
                )

            # 3️⃣ Login user
            login(request, user, 'django.contrib.auth.backends.ModelBackend')
            UserLoginActivity.objects.create(user=user,ip_address=get_client_ip(request))
            if user.is_superuser:
                return redirect('storageapp:admin_dashboard')
            else:
                return redirect('storageapp:dashboard')
        else:
            prefill = {
                'name': name,
                'phone': phone,
                'email': email,
                'userid':userid,
                "password": password,
                "confirmpassword" : confirm_password
            }
            request.session['signupprefill'] = prefill
            return redirect('accounts:signup_page')
        

def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0]
    return request.META.get("REMOTE_ADDR")
        

@login_required
def user_logout(request):
    logout(request)  
    return redirect('accounts:signin_page')


@login_required
def post_login_redirect(request):
    if request.user.is_superuser:
        return redirect("storageapp:admin_dashboard")

    return redirect("storageapp:dashboard")



        
    
