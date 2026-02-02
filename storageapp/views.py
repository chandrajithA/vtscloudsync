from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
import cloudinary.uploader
from .models import *
import mimetypes
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Sum
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.contrib.auth import get_user_model
import requests
from django.http import StreamingHttpResponse, Http404
from subscriptions.models import UserSubscription
from django.db.models import Q
from accounts.models import UserLoginActivity
from django.db.models.functions import TruncMonth
from django.db.models.functions import TruncDate
from datetime import date
from django.urls import reverse
from django.template.defaultfilters import filesizeformat
import json
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.contrib import messages



User = get_user_model()

def is_admin(user):
    return user.is_superuser

MAX_SIMPLE_UPLOAD = 4 * 1024 * 1024


def dashboard(request):
    if request.user.is_authenticated and not request.user.is_superuser:
        user = request.user

        # Exclude trashed files
        files = CloudFile.objects.filter(user=user, is_deleted=False)

        # ---- STORAGE CARDS ----
        stats = {
            "document": files.filter(file_type="document"),
            "image": files.filter(file_type="image"),
            "video": files.filter(file_type="video"),
            "other": files.filter(file_type="other"),
        }

        cards = {}
        for key, qs in stats.items():
            cards[key] = {
                "count": qs.count(),
                "size": qs.aggregate(total=Sum("file_size"))["total"] or 0
            }

        # ---- RECENT FILES ----
        recent_files = files.order_by("-uploaded_at")[:6]

        return render(request, "storageapp/dashboard.html", {
            "cards": cards,
            "recent_files": recent_files
        })
    elif request.user.is_authenticated and request.user.is_superuser:
        return redirect('storageapp:admin_dashboard')
    else:
        return redirect('accounts:signin_page')




@login_required
def admin_dashboard(request):
    if request.user.is_authenticated and request.user.is_superuser:
        total_users = User.objects.count()
        active_files = CloudFile.objects.filter(is_deleted=False)
        total_files = active_files.count()
        storage_used = active_files.aggregate(total=models.Sum("file_size"))["total"] or 0

        # Plan distribution
        plan_stats = (
            UserSubscription.objects
            .values("plan__name")
            .annotate(count=Count("id"))
        )

        recent_activity = (
            CloudFile.objects
            .select_related("user")
            .order_by("-uploaded_at")[:5]
        )

        return render(request, "adminpanel/dashboard.html", {
            "total_users": total_users,
            "total_files": total_files,
            "storage_used": storage_used,
            "plan_stats": plan_stats,
            "recent_activity": recent_activity,
        })
    elif request.user.is_authenticated and not request.user.is_superuser:
        return redirect('storageapp:dashboard')
    else:
        return redirect('accounts:signin_page')


@login_required
def admin_user_activity_api(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    # ✅ Use local date (Asia/Kolkata safe)
    today = timezone.localdate()

    # Last 7 IST dates
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]

    # ✅ Group logins by local date
    qs = (
        UserLoginActivity.objects
        .annotate(
            login_date=TruncDate(
                "login_at",
                tzinfo=timezone.get_current_timezone()
            )
        )
        .values("login_date")
        .annotate(count=Count("id"))
    )

    # Convert queryset → dict
    data_map = {
        item["login_date"]: item["count"]
        for item in qs
    }

    labels = []
    data = []

    for day in last_7_days:
        labels.append(day.strftime("%a"))  # Sun, Mon
        data.append(data_map.get(day, 0))

    return JsonResponse({
        "labels": labels,
        "data": data
    })


@login_required
def admin_plan_distribution_api(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    qs = (
        UserSubscription.objects
        .values("plan__name")
        .annotate(count=Count("id"))
    )

    labels = [x["plan__name"] for x in qs]
    data = [x["count"] for x in qs]

    return JsonResponse({
        "labels": labels,
        "data": data
    })


@login_required
def admin_storage_growth_api(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    # ✅ Always use timezone-aware "now"
    today = timezone.localdate()   # IST-safe

    # First day of current month (IST)
    current_month = today.replace(day=1)

    # Generate last 12 calendar months (IST-safe)
    months = []
    year, month = current_month.year, current_month.month
    for _ in range(12):
        months.insert(0, date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    # 🔹 Truncate uploaded_at in DB (UTC → IST handled by Django)
    qs = (
        CloudFile.objects
        .filter(is_deleted=False)
        .annotate(month=TruncMonth("uploaded_at", tzinfo=timezone.get_current_timezone()))
        .values("month")
        .annotate(total_size=Sum("file_size"))
    )

    storage_map = {
        item["month"].date(): item["total_size"]
        for item in qs
    }

    labels = []
    data = []

    for m in months:
        labels.append(m.strftime("%b %Y"))   # Jan 2026
        size = storage_map.get(m, 0)
        mb = size / (1024 * 1024)
        data.append(round(mb, 2))

    return JsonResponse({
        "labels": labels,
        "data": data
    })



def upload_page(request):
    if request.user.is_authenticated:
        if request.method == 'GET':
            if request.user.is_superuser:
                base_template = "adminpanel/admin_base.html"
            else:
                base_template = "storageapp/base.html"

            # 👇 IMPORTANT PART
            last_uploads = (
                CloudFile.objects
                .filter(user=request.user, is_deleted=False)
                .order_by("-uploaded_at")[:10]
            )

            return render(
                request,
                "storageapp/upload.html",
                {"last_uploads": last_uploads,
                "base_template": base_template},
            )
            
        if request.method == 'POST':
            file = request.FILES.get('file')

            if not file:
                return render(request, "storageapp/upload.html", {
                    "error": "Please select a file",
                    "base_template": base_template
                })
            
            used = (
                    CloudFile.objects
                    .filter(user=request.user, is_deleted=False)
                    .aggregate(total=Sum("file_size"))["total"] or 0
                )

            sub = UserSubscription.objects.select_related("plan").filter(user=request.user).first()
            limit = sub.plan.storage_limit if sub and sub.plan else 0
            file_size_limit = sub.plan.file_size_lmt if sub and sub.plan.file_size_lmt else None

            remaining_space = limit - used

            if remaining_space <= 0:
                return JsonResponse(
                    {"error": "Storage almost full. Upgrade your plan."},
                    status=403
                )

            
            # 🚫 If this file does not fit, skip it
            if file.size > remaining_space:
                UploadHistory.objects.create(
                    user=request.user,
                    file_name=file.name,
                    file_size=file.size,
                    status="failed",
                    failure_reason="STORAGE_FULL",
                    failure_message="Not enough storage",
                    ip_address=get_client_ip(request),
                )
                return JsonResponse({
                    "success": True,
                    "rejected_files": [{
                        "name": file.name,
                        "reason": "Not enough storage"
                    }]
                })

            if file_size_limit and file.size > file_size_limit:
                UploadHistory.objects.create(
                    user=request.user,
                    file_name=file.name,
                    file_size=file.size,
                    status="failed",
                    failure_reason="FILE_TOO_LARGE",
                    failure_message=f"File should be less than {filesizeformat(file_size_limit)}",
                    ip_address=get_client_ip(request),
                )
                return JsonResponse({
                    "success": True,
                    "rejected_files": [{
                        "name": file.name,
                        "reason": f"File should be less than {filesizeformat(file_size_limit)}"
                    }]
                })

            
        
            mime_type, _ = mimetypes.guess_type(file.name)

            uploaded_file = None
            file_url = None
            public_id = None

            if mime_type and mime_type.startswith("image"):
                file_type = "image"
                try:
                    if file.size > MAX_SIMPLE_UPLOAD:
                        # 🔥 LARGE FILE
                        result = cloudinary.uploader.upload_large(
                            file,
                            resource_type="raw",
                            folder="images",
                            use_filename=True,
                            unique_filename=True,
                            chunk_size=6000000
                        )
                        file_url = result["secure_url"]
                        public_id = result["public_id"] 
                    else:
                        # 🔹 SMALL FILE
                        result = cloudinary.uploader.upload(
                            file,
                            resource_type="raw",
                            folder="images",
                            use_filename=True,
                            unique_filename=True,
                        )
                        file_url = result["secure_url"]
                        public_id = result["public_id"] 

                except Exception:
                    UploadHistory.objects.create(
                        user=request.user,
                        file_name=file.name,
                        file_size=file.size,
                        status="failed",
                        failure_reason="CLOUDINARY_LIMIT",
                        failure_message="Cloudinary rejected file (size limit exceeded)",
                        ip_address=get_client_ip(request),
                    )
                    return JsonResponse({
                        "success": True,
                        "rejected_files": [{
                            "name": file.name,
                            "reason": "Cloudinary rejected file (size limit exceeded)"
                        }]
                    })

            # ✅ VIDEO
            elif mime_type and mime_type.startswith("video"):
                file_type = "video"
                try:
                    if file.size > MAX_SIMPLE_UPLOAD:
                        # 🔥 LARGE FILE
                        result = cloudinary.uploader.upload_large(
                            file,
                            resource_type="raw",
                            folder="videos",
                            use_filename=True,
                            unique_filename=True,
                            chunk_size=6000000
                        )
                        file_url = result["secure_url"]
                        public_id = result["public_id"] 
                    else:
                        # 🔹 SMALL FILE
                        result = cloudinary.uploader.upload(
                            file,
                            resource_type="raw",
                            folder="videos",
                            use_filename=True,
                            unique_filename=True,
                        )
                        file_url = result["secure_url"]
                        public_id = result["public_id"] 

                except Exception:
                    
                    UploadHistory.objects.create(
                        user=request.user,
                        file_name=file.name,
                        file_size=file.size,
                        status="failed",
                        failure_reason="CLOUDINARY_LIMIT",
                        failure_message="Cloudinary rejected file (size limit exceeded)",
                        ip_address=get_client_ip(request),
                    )
                    return JsonResponse({
                        "success": True,
                        "rejected_files": [{
                            "name": file.name,
                            "reason": "Cloudinary rejected file (size limit exceeded)"
                        }]
                    })
                

            # ✅ PDF
            elif mime_type == "application/pdf":
                file_type = "document"
                try:
                    if file.size > MAX_SIMPLE_UPLOAD:
                        # 🔥 LARGE FILE
                        result = cloudinary.uploader.upload_large(
                            file,
                            resource_type="raw",
                            folder="PDFs",
                            use_filename=True,
                            unique_filename=True,
                            chunk_size=6000000
                        )
                        file_url = result["secure_url"]
                        public_id = result["public_id"] 
                    else:
                        # 🔹 SMALL FILE
                        result = cloudinary.uploader.upload(
                            file,
                            resource_type="raw",
                            folder="PDFs",
                            use_filename=True,
                            unique_filename=True,
                        )
                        file_url = result["secure_url"]
                        public_id = result["public_id"] 
                
                except Exception as e:
                    UploadHistory.objects.create(
                        user=request.user,
                        file_name=file.name,
                        file_size=file.size,
                        status="failed",
                        failure_reason="CLOUDINARY_LIMIT",
                        failure_message="Cloudinary rejected file (size limit exceeded)",
                        ip_address=get_client_ip(request),
                    )
                    return JsonResponse({
                        "success": True,
                        "rejected_files": [{
                            "name": file.name,
                            "reason": "Cloudinary rejected file (size limit exceeded)"
                        }]
                    })
                

            # ✅ OTHER FILES
            else:
                file_type = "other"
                try:
                    if file.size > MAX_SIMPLE_UPLOAD:
                        # 🔥 LARGE FILE
                        result = cloudinary.uploader.upload_large(
                            file,
                            resource_type="raw",
                            folder="documents",
                            use_filename=True,
                            unique_filename=True,
                            chunk_size=6000000
                        )
                        file_url = result["secure_url"]
                        public_id = result["public_id"] 
                    else:
                        # 🔹 SMALL FILE
                        result = cloudinary.uploader.upload(
                            file,
                            resource_type="raw",
                            folder="documents",
                            use_filename=True,
                            unique_filename=True,
                        )
                        file_url = result["secure_url"]
                        public_id = result["public_id"] 

                except Exception as e:
                    
                    UploadHistory.objects.create(
                        user=request.user,
                        file_name=file.name,
                        file_size=file.size,
                        status="failed",
                        failure_reason="CLOUDINARY_LIMIT",
                        failure_message="Cloudinary rejected file (size limit exceeded)",
                        ip_address=get_client_ip(request),
                    )
                    return JsonResponse({
                        "success": True,
                        "rejected_files": [{
                            "name": file.name,
                            "reason": "Cloudinary rejected file (size limit exceeded)"
                        }]
                    })
                

            CloudFile.objects.create(
                user=request.user,
                file_name=file.name,
                file_size=file.size,
                file_type=file_type,
                uploaded_file=uploaded_file,
                file_url=file_url,
                public_id=public_id,
            )

            UploadHistory.objects.create(
                user=request.user,
                file_name=file.name,
                file_size=file.size,
                file_type=file_type,
                mime_type=mime_type,
                status="success",
                file_url=file_url,
                public_id=public_id,
                ip_address=get_client_ip(request),
            )

        return JsonResponse({
            "success": True,
            "uploaded_files": [file.name],
            "rejected_files": []
        })
        
    else: 
        next_url = reverse('storageapp:upload_page')
        request.session['next_url'] = next_url
        return redirect('accounts:signin_page')
    

@require_POST
@login_required
def upload_cancelled(request):
    file_name = request.POST.get("file_name")
    file_size = request.POST.get("file_size")

    UploadHistory.objects.create(
        user=request.user,
        file_name=file_name,
        file_size=file_size,
        status="cancelled",
        failure_reason="CANCELLED",
        failure_message="User cancelled upload",
        ip_address=get_client_ip(request),
    )

    return JsonResponse({"success": True})
    

def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0]
    return request.META.get("REMOTE_ADDR")



def shared_files(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            base_template = "adminpanel/admin_base.html"
        else:
            base_template = "storageapp/base.html"

        shared_with_me = SharedFile.objects.filter(
            shared_with=request.user,
            file__is_deleted=False
        ).select_related("file", "owner")

        shared_by_me = SharedFile.objects.filter(
            owner=request.user,
            file__is_deleted=False
        ).select_related("file", "shared_with")

        total_shared = shared_by_me.count() + shared_with_me.count()

        return render(request, "storageapp/shared.html", {
            "shared_with_me": shared_with_me,
            "shared_by_me": shared_by_me,
            "total_shared":total_shared,
            "base_template": base_template,
        })
    else: 
        next_url = reverse('storageapp:shared_files')
        request.session['next_url'] = next_url
        return redirect('accounts:signin_page')


@require_POST
@login_required
def share_file_api(request, file_id):
    file = get_object_or_404(
        CloudFile,
        id=file_id,
        user=request.user,
        is_deleted=False
    )

    username = request.POST.get("username")

    if not username:
        return JsonResponse({"success": False, "error": "Username required"})

    try:
        target_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "User not found"})

    if target_user == request.user:
        return JsonResponse({"success": False, "error": "Cannot share with yourself"})

    SharedFile.objects.get_or_create(
        file=file,
        owner=request.user,
        shared_with=target_user
    )

    return JsonResponse({"success": True})
    




def myfiles(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            base_template = "adminpanel/admin_base.html"
        else:
            base_template = "storageapp/base.html"
        q = request.GET.get("q", "").strip()
        file_type = request.GET.get("type")

        files = CloudFile.objects.filter(
            user=request.user,
            is_deleted=False
        )

        # 🔹 Filter by category
        if file_type:
            files = files.filter(file_type=file_type)

        # 🔹 Search inside selected category
        if q:
            files = files.filter(file_name__icontains=q)

        files = files.order_by("-uploaded_at")

        return render(
            request,
            "storageapp/myfiles.html",
            {
                "files": files,
                "active_type": file_type,
                "base_template": base_template,
            }
        )
    else: 
        next_url = reverse('storageapp:myfiles')
        request.session['next_url'] = next_url
        return redirect('accounts:signin_page')




def trash(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            base_template = "adminpanel/admin_base.html"
        else:
            base_template = "storageapp/base.html"

        query = request.GET.get("q", "")

        files = CloudFile.objects.filter(
            user=request.user,
            is_deleted=True
        )

        if query:
            files = files.filter(
                Q(file_name__icontains=query) |
                Q(file_type__icontains=query)
            )

        total_size = sum(f.file_size for f in files)
        expiring_soon = sum(
            1 for f in files if f.days_left() is not None and f.days_left() <= 7
        )

        return render(request, "storageapp/trash.html", {
            "files": files,
            "total_files": files.count(),
            "total_size": total_size,
            "expiring_soon": expiring_soon,
            "query": query,
            "base_template": base_template,
        })
    else: 
        next_url = reverse('storageapp:trash')
        request.session['next_url'] = next_url
        return redirect('accounts:signin_page')



def trash_stats(user):
    files = CloudFile.objects.filter(user=user, is_deleted=True)

    return {
        "count": files.count(),
        "size": sum(f.file_size for f in files),
        "expiring": sum(
            1 for f in files
            if f.days_left() is not None and f.days_left() <= 7
        )
    }




def settings_page(request):

    if request.user.is_authenticated:

        user = request.user

        if request.user.is_superuser:
            base_template = "adminpanel/admin_base.html"
        else:
            base_template = "storageapp/base.html"

        if request.method == "POST":

        # ==========================
        # 🔐 PASSWORD FORM (FIRST!)
        # ==========================
            if "password_form" in request.POST:
                new_password = request.POST.get("new_password")
                confirm_password = request.POST.get("confirm_password")
                current_password = request.POST.get("current_password")

                if new_password != confirm_password:
                    messages.error(request, "Passwords do not match.")
                    return redirect("storageapp:settings_page")

                if user.has_usable_password():
                    if not current_password:
                        messages.error(request, "Current password is required.")
                        return redirect("storageapp:settings_page")

                    if not check_password(current_password, user.password):
                        messages.error(request, "Current password is incorrect.")
                        return redirect("storageapp:settings_page")

                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)

                messages.success(request, "Password updated successfully.")
                return redirect("storageapp:settings_page")

            # ==========================
            # 🖼 REMOVE PHOTO
            # ==========================
            if "remove_photo" in request.POST:
                if user.profile_picture:
                    user.profile_picture.delete(save=False)
                    user.profile_picture = None
                    user.save()
                return redirect("storageapp:settings_page")

            # ==========================
            # 👤 PROFILE UPDATE ONLY
            # ==========================
            if request.FILES.get("profile_picture"):
                user.profile_picture = request.FILES["profile_picture"]

            user.first_name = request.POST.get("first_name", user.first_name)
            user.last_name = request.POST.get("last_name", user.last_name)
            user.email = request.POST.get("email", user.email)
            user.phone = request.POST.get("phone", user.phone)

            user.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("storageapp:settings_page")

        return render(
            request,
            "storageapp/settings.html",
            {"base_template": base_template},
        )
    else: 
        next_url = reverse('storageapp:settings_page')
        request.session['next_url'] = next_url
        return redirect('accounts:signin_page')
    

@login_required
def check_username(request):
    username = request.GET.get("username", "").strip()
    exists = User.objects.filter(username=username).exclude(id=request.user.id).exists()
    return JsonResponse({"available": not exists})


@login_required
@require_POST
def update_username(request):
    data = json.loads(request.body)
    username = data.get("username", "").strip()

    if not username:
        return JsonResponse({"success": False, "message": "Username required"})

    if User.objects.filter(username=username).exclude(id=request.user.id).exists():
        return JsonResponse({"success": False, "message": "Username already taken"})

    request.user.username = username
    request.user.save()
    return JsonResponse({"success": True, "message": "Username updated successfully"})




@require_POST
@login_required
def move_to_trash(request, file_id):
    
    file = get_object_or_404(CloudFile, id=file_id, user=request.user)
    file.is_deleted = True
    file.deleted_at = timezone.now()
    file.save()

    files = CloudFile.objects.filter(user=request.user, is_deleted=False)

    stats = {
        "document": {
            "count": files.filter(file_type="document").count(),
            "size": files.filter(file_type="document")
                          .aggregate(s=Sum("file_size"))["s"] or 0
        },
        "image": {
            "count": files.filter(file_type="image").count(),
            "size": files.filter(file_type="image")
                          .aggregate(s=Sum("file_size"))["s"] or 0
        },
        "video": {
            "count": files.filter(file_type="video").count(),
            "size": files.filter(file_type="video")
                          .aggregate(s=Sum("file_size"))["s"] or 0
        },
        "other": {
            "count": files.filter(file_type="other").count(),
            "size": files.filter(file_type="other")
                          .aggregate(s=Sum("file_size"))["s"] or 0
        },
    }

    return JsonResponse({
        "success": True,
        "stats": stats
    })





@login_required
def download_file(request, file_id):
    file = CloudFile.objects.filter(
        id=file_id,
        is_deleted=False
    ).filter(
        Q(user=request.user) |
        Q(shared_entries__shared_with=request.user)
    ).distinct().first()

    if not file:
        raise Http404("File not accessible")

    r = requests.get(file.file_url, stream=True, timeout=30)
    r.raise_for_status()

    response = StreamingHttpResponse(
        r.iter_content(chunk_size=8192),
        content_type=r.headers.get("Content-Type", "application/octet-stream"),
    )
    response["Content-Disposition"] = f'attachment; filename="{file.file_name}"'
    response["Content-Length"] = r.headers.get("Content-Length", "")
    return response





@require_POST
@login_required
def remove_shared_file(request, shared_id):
    shared = get_object_or_404(
        SharedFile,
        id=shared_id
    )

    # 🔐 Security check
    if request.user == shared.shared_with:
        # ✅ ONLY remove share entry
        shared.delete()
        return JsonResponse({"success": True})
    else:
        return JsonResponse({"success": False, "error": "Not allowed"})

    

    


@require_POST
@login_required
def remove_shared_own_file(request, shared_id):
    shared = get_object_or_404(
        SharedFile,
        id=shared_id
    )

    # 🔐 Security check
    if request.user == shared.owner:
        # ✅ ONLY remove share entry
        shared.delete()
        return JsonResponse({"success": True})
    else:
        return JsonResponse({"success": False, "error": "Not allowed"})

    



@login_required
def restore_file(request, file_id):
    file = get_object_or_404(
        CloudFile, id=file_id, user=request.user, is_deleted=True
    )

    used = (
        CloudFile.objects
        .filter(user=request.user, is_deleted=False)
        .aggregate(total=Sum("file_size"))["total"] or 0
    )

    sub = UserSubscription.objects.select_related("plan").filter(user=request.user).first()
    limit = sub.plan.storage_limit if sub and sub.plan else 0

    remaining_space = limit - used

    

    if remaining_space <= 0:
        return JsonResponse(
            {"error": "Storage almost full. Upgrade your plan."},
            status=403
        )
    
    if file.file_size > remaining_space:
        return JsonResponse(
            {"error": "Storage almost full. Upgrade your plan."},
            status=403
        )


    file.is_deleted = False
    file.deleted_at = None
    file.save()

    return JsonResponse({
        "success": True,
        "stats": trash_stats(request.user)
    })



@login_required
def restore_all(request):
    user = request.user

    # 1️⃣ Currently used storage
    used = (
        CloudFile.objects
        .filter(user=user, is_deleted=False)
        .aggregate(total=Sum("file_size"))["total"] or 0
    )

    # 2️⃣ Total size of deleted files
    deleted_total = (
        CloudFile.objects
        .filter(user=user, is_deleted=True)
        .aggregate(total=Sum("file_size"))["total"] or 0
    )

    # 3️⃣ Get storage limit
    sub = UserSubscription.objects.select_related("plan").filter(user=user).first()
    limit = sub.plan.storage_limit if sub and sub.plan else 0

    remaining_space = limit - used

    if remaining_space <= 0:
        return JsonResponse(
            {"error": "Storage almost full. Upgrade your plan."},
            status=403
        )

    # 4️⃣ Check if restore fits
    if deleted_total > remaining_space:
        return JsonResponse(
            {
                "error": "Not enough storage to restore all files. Restore files individually or upgrade your plan."
            },
            status=403
        )

    # 5️⃣ Restore all
    CloudFile.objects.filter(user=user, is_deleted=True).update(
        is_deleted=False,
        deleted_at=None
    )

    return JsonResponse({
        "success": True,
        "message": "All files restored successfully",
        "stats": trash_stats(user)
    })



@login_required
def delete_file(request, file_id):
    file = get_object_or_404(
        CloudFile, id=file_id, user=request.user, is_deleted=True
    )

    # delete from cloudinary
    cloudinary.uploader.destroy(
        file.public_id,
        resource_type="raw"
    )

    file.delete()

    return JsonResponse({
        "success": True,
        "stats": trash_stats(request.user)
    })





@login_required
def empty_trash(request):
    files = CloudFile.objects.filter(user=request.user, is_deleted=True)

    for file in files:
        cloudinary.uploader.destroy(
            file.public_id,
            resource_type="raw"
        )

    files.delete()
    return JsonResponse({
        "success": True,
        "message": "Trash emptied successfully"
    })