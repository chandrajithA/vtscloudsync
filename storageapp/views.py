from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import *
import mimetypes
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Sum
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.http import Http404
from subscriptions.models import UserSubscription
from django.db.models import Q
from accounts.models import UserLoginActivity
from datetime import date
from django.template.defaultfilters import filesizeformat
import json
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.contrib import messages
from .s3_utils import *
from django.core.cache import cache
from storageapp.utils import cleanup_trash
from collections import defaultdict



User = get_user_model()

# def is_admin(user):
#     return user.is_superuser


@login_required
def dashboard(request):
    run_daily_cleanup()
    if not request.user.is_superuser:
        user = request.user

        # Exclude trashed files
        files = CloudFile.objects.filter(user=user, organization=None, is_deleted=False)

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
    elif request.user.is_superuser:
        return redirect('storageapp:admin_dashboard')




@login_required
def admin_dashboard(request):
    run_daily_cleanup()
    if request.user.is_superuser:
        users = User.objects.filter()
        total_users = users.count()
        active_users = users.filter(is_active=True).count()
        total_files=CloudFile.objects.filter()
        total_files_count=total_files.count()
        total_storage_used = total_files.aggregate(total=models.Sum("file_size"))["total"] or 0
        user_active_files = CloudFile.objects.filter(organization=None,is_deleted=False)
        user_active_files_count = user_active_files.count()
        user_active_storage = user_active_files.aggregate(total=models.Sum("file_size"))["total"] or 0
        user_deleted_files = CloudFile.objects.filter(organization=None,is_deleted=True)
        user_deleted_files_count = user_deleted_files.count()
        user_trash_storage = user_deleted_files.aggregate(total=models.Sum("file_size"))["total"] or 0
        total_organization = Organization.objects.count()
        org_active_files = CloudFile.objects.filter(organization__isnull=False,is_deleted=False)
        org_active_files_count = org_active_files.count()
        org_active_storage = org_active_files.aggregate(total=models.Sum("file_size"))["total"] or 0
        org_deleted_files = CloudFile.objects.filter(organization__isnull=False,is_deleted=True)
        org_deleted_files_count = org_deleted_files.count()
        org_trash_storage = org_deleted_files.aggregate(total=models.Sum("file_size"))["total"] or 0
        # Plan distribution
        plan_stats = (
            UserSubscription.objects
            .values("plan__name")
            .annotate(count=Count("id"))
        )

        recent_activity = (
            FileHistory.objects
            .select_related("user")
            .order_by("-created_at")
        )

        return render(request, "adminpanel/super-admin-dashboard.html", {
            "total_users": total_users,
            "active_users": active_users,
            "total_files_count": total_files_count,
            "total_storage_used": total_storage_used,
            "user_active_files_count": user_active_files_count,
            "user_active_storage": user_active_storage,
            "user_deleted_files_count": user_deleted_files_count,
            "user_trash_storage": user_trash_storage,
            "total_organization": total_organization,
            "org_active_files_count": org_active_files_count,
            "org_active_storage": org_active_storage,
            "org_deleted_files_count": org_deleted_files_count,
            "org_trash_storage": org_trash_storage,
            "recent_activity": recent_activity,
        })
    else:
        return redirect('storageapp:dashboard')


@login_required
def super_admin_user_activity_api(request):
    if request.user.is_superuser:
       

        # ✅ Use local date (Asia/Kolkata safe)
        today = timezone.localdate()

        # Last 7 IST dates
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]

        # Fetch login records
        activities = UserLoginActivity.objects.all()

        # Group in Python
        data_map = defaultdict(int)

        for act in activities:
            local_day = timezone.localtime(act.login_at).date()
            data_map[local_day] += 1

        labels = []
        data = []

        for day in last_7_days:
            labels.append(day.strftime("%a"))  # Sun, Mon, Tue
            data.append(data_map.get(day, 0))

        return JsonResponse({
            "labels": labels,
            "data": data
        })
    else:
        return JsonResponse({"error": "Unauthorized"}, status=403)





@login_required
def super_admin_plan_distribution_api(request):
    if request.user.is_superuser:
        
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
    else:
        return JsonResponse({"error": "Unauthorized"}, status=403)






@login_required
def super_admin_storage_growth_api(request):
    if request.user.is_superuser:

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

        # fetch files
        files = CloudFile.objects.filter()

        storage_map = {}

        for f in files:
            local_date = timezone.localtime(f.uploaded_at).date()
            key = local_date.replace(day=1)
            storage_map[key] = storage_map.get(key, 0) + f.file_size

        labels = []
        data = []

        for m in months:
            labels.append(m.strftime("%b %Y"))
            size = storage_map.get(m, 0)
            mb = size / (1024 * 1024)
            data.append(round(mb, 2))

        return JsonResponse({
            "labels": labels,
            "data": data
        })
    else:
        return JsonResponse({"error": "Unauthorized"}, status=403)



@login_required
def org_admin_dashboard(request):
    org_member = request.user.org_membership
    org = request.user.org_membership.organization
    if org_member and org and org_member.is_admin and org_member.is_active and org.is_active:
        users = User.objects.filter(org_membership__organization=org)
        total_users = users.count()
        active_users = users.filter(is_active=True).count()
        total_files=CloudFile.objects.filter(organization=org)
        total_files_count=total_files.count()
        total_storage_used = total_files.aggregate(total=models.Sum("file_size"))["total"] or 0
        org_active_files = CloudFile.objects.filter(organization=org,is_deleted=False)
        org_active_files_count = org_active_files.count()
        org_active_storage = org_active_files.aggregate(total=models.Sum("file_size"))["total"] or 0
        org_deleted_files = CloudFile.objects.filter(organization=org,is_deleted=True)
        org_deleted_files_count = org_deleted_files.count()
        org_trash_storage = org_deleted_files.aggregate(total=models.Sum("file_size"))["total"] or 0
        # Plan distribution
        plan_stats = (
            UserSubscription.objects.filter(user__org_membership__organization=org)
            .values("plan__name")
            .annotate(count=Count("user", distinct=True))
        )

        recent_activity = (
            FileHistory.objects.filter(organization=org)
            .select_related("user","organization")
            .order_by("-created_at")
        )

        return render(request, "adminpanel/org-admin-dashboard.html", {
            "total_users": total_users,
            "active_users": active_users,
            "total_files_count": total_files_count,
            "total_storage_used": total_storage_used,
            "org_active_files_count": org_active_files_count,
            "org_active_storage": org_active_storage,
            "org_deleted_files_count": org_deleted_files_count,
            "org_trash_storage": org_trash_storage,
            "recent_activity": recent_activity,
        })
    elif request.user.is_superuser:
        return redirect('storageapp:admin_dashboard')
    else:
        return redirect('storageapp:dashboard')
    




@login_required
def org_admin_user_activity_api(request):
    org_member = request.user.org_membership
    org = request.user.org_membership.organization
    if org_member and org and org_member.is_admin and org_member.is_active and org.is_active:
        

        # ✅ Use local date (Asia/Kolkata safe)
        today = timezone.localdate()

        # Last 7 IST dates
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]

        # Fetch login records
        activities = UserLoginActivity.objects.filter(
                    user__org_membership__organization=org,
                    user__org_membership__is_active=True
                )

        # Group in Python
        data_map = defaultdict(int)

        for act in activities:
            local_day = timezone.localtime(act.login_at).date()
            data_map[local_day] += 1

        labels = []
        data = []

        for day in last_7_days:
            labels.append(day.strftime("%a"))  # Sun, Mon, Tue
            data.append(data_map.get(day, 0))

        return JsonResponse({
            "labels": labels,
            "data": data
        })
    else:
        return JsonResponse({"error": "Unauthorized"}, status=403)





@login_required
def org_admin_plan_distribution_api(request):
    org_member = request.user.org_membership
    org = request.user.org_membership.organization
    if org_member and org and org_member.is_admin and org_member.is_active and org.is_active:

        qs = (
            UserSubscription.objects.filter(
                    user__org_membership__organization=org,
                    user__org_membership__is_active=True
                )
            .values("plan__name")
            .annotate(count=Count("id"))
        )

        labels = [x["plan__name"] for x in qs]
        data = [x["count"] for x in qs]

        return JsonResponse({
            "labels": labels,
            "data": data
        })
    else:
        return JsonResponse({"error": "Unauthorized"}, status=403)






@login_required
def org_admin_storage_growth_api(request):
    org_member = request.user.org_membership
    org = request.user.org_membership.organization
    if org_member and org and org_member.is_admin and org_member.is_active and org.is_active:

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

        # fetch files
        files = CloudFile.objects.filter(organization=org)

        storage_map = {}

        for f in files:
            local_date = timezone.localtime(f.uploaded_at).date()
            key = local_date.replace(day=1)
            storage_map[key] = storage_map.get(key, 0) + f.file_size

        labels = []
        data = []

        for m in months:
            labels.append(m.strftime("%b %Y"))
            size = storage_map.get(m, 0)
            mb = size / (1024 * 1024)
            data.append(round(mb, 2))

        return JsonResponse({
            "labels": labels,
            "data": data
        })
    else:
        return JsonResponse({"error": "Unauthorized"}, status=403)


    

@login_required
def upload_page(request):
    if request.method == 'GET':
        if request.user.is_superuser:
            base_template = "adminpanel/admin_base.html"
        else:
            base_template = "storageapp/base.html"

        # 👇 IMPORTANT PART
        recent_uploads = (
            FileHistory.objects
            .filter(user=request.user,organization=None)
            .order_by("-created_at")[:10]
        )

        return render(
            request,
            "storageapp/upload.html",
            {"recent_uploads": recent_uploads,
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
        if sub:
            if sub.plan:
                limit = sub.plan.storage_limit
                file_size_limit = sub.plan.file_size_lmt
            else:
                limit = 0
                file_size_limit = 0
        else:
            limit = 0
            file_size_limit = 0
        

        if limit is not None or file_size_limit is not None:
            if limit == 0 or file_size_limit == 0:
                FileHistory.objects.create(
                    user=request.user,
                    organization=None,
                    file_name=file.name,
                    file_size=file.size,
                    file_type="other",
                    action="upload",
                    status="failed",
                    failure_reason="PLAN_ERROR",
                    failure_message="Error in Plan configuration or storage. Contact admin.",
                    ip_address=get_client_ip(request),
                )
                return JsonResponse({
                    "success": True,
                    "rejected_files": [{
                        "name": file.name,
                        "reason": "Error in Plan configuration or storage. Contact admin."
                    }]
                })
            
            if limit is not None:
                remaining_space = limit - used

                if remaining_space <= 0:
                    FileHistory.objects.create(
                        user=request.user,
                        organization=None,
                        file_name=file.name,
                        file_size=file.size,
                        file_type="other",
                        action="upload",
                        status="failed",
                        failure_reason="STORAGE_FULL",
                        failure_message="Not enough storage. Upgrade plan.",
                        ip_address=get_client_ip(request),
                    )
                    return JsonResponse({
                        "success": True,
                        "rejected_files": [{
                            "name": file.name,
                            "reason": "Storage almost full. Upgrade your plan."
                        }]
                    })
            
            
                # 🚫 If this file does not fit, skip it
                if file.size > remaining_space:
                    FileHistory.objects.create(
                        user=request.user,
                        organization=None,
                        file_name=file.name,
                        file_size=file.size,
                        file_type="other",
                        action="upload",
                        status="failed",
                        failure_reason="STORAGE_FULL",
                        failure_message="Not enough storage. Upgrade plan.",
                        ip_address=get_client_ip(request),
                    )
                    return JsonResponse({
                        "success": True,
                        "rejected_files": [{
                            "name": file.name,
                            "reason": "Not enough storage. Upgrade plan."
                        }]
                    })
            
            if file_size_limit is not None:
        
                if file.size > file_size_limit:
                    FileHistory.objects.create(
                        user=request.user,
                        organization=None,
                        file_name=file.name,
                        file_size=file.size,
                        file_type="other",
                        action="upload",
                        status="failed",
                        failure_reason="FILE_TOO_LARGE",
                        failure_message=f"File Size Limit - {filesizeformat(file_size_limit)} for this plan",
                        ip_address=get_client_ip(request),
                    )
                    return JsonResponse({
                        "success": True,
                        "rejected_files": [{
                            "name": file.name,
                            "reason": f"File Size Limit - {filesizeformat(file_size_limit)} for this plan"
                        }]
                    })


        mime_type, _ = mimetypes.guess_type(file.name)

        if mime_type and mime_type.startswith("image"):
            file_type = "image"
            folder = "images"
        
        elif mime_type and mime_type.startswith("video"):
            file_type = "video"
            folder = "videos"

        elif mime_type == "application/pdf":
            file_type = "document"
            folder = "pdfs"

        else:
            file_type = "other"
            folder = "documents"

        try:
            print("Uploading to S3...")
            file_url, s3_key = upload_to_s3(file, folder) 
            print("Upload success")

        except Exception as e:
            import traceback
            print("FULL ERROR:")
            traceback.print_exc()
            FileHistory.objects.create(
                user=request.user,
                organization=None,
                file_name=file.name,
                file_size=file.size,
                file_type=file_type,
                action="upload",
                status="failed",
                failure_reason="S3_UPLOAD_FAILED",
                failure_message="Upload Failed at storage. Contact Admin",
                failure_comment=str(e),
                ip_address=get_client_ip(request),
            )
            return JsonResponse({
                "success": True,
                "rejected_files": [{
                    "name": file.name,
                    "reason": "Upload Failed at storage. Contact Admin"
                }]
            })  

        CloudFile.objects.create(
            user=request.user,
            organization=None,
            file_name=file.name,
            file_size=file.size,
            file_type=file_type,
            file_url=generate_presigned_url(
                        s3_key,
                        filename=file.name
                    ),
            public_id=s3_key,
        )

        FileHistory.objects.create(
            user=request.user,
            organization=None,
            file_name=file.name,
            file_size=file.size,
            file_type=file_type,
            mime_type=mime_type,
            action="upload",
            status="success",
            file_url=file_url,
            public_id=s3_key,
            ip_address=get_client_ip(request),
        )

    return JsonResponse({
        "success": True,
        "uploaded_files": [file.name],
        "rejected_files": []
    })
        
    

@require_POST
@login_required
def upload_cancelled(request):
    file_name = request.POST.get("file_name")
    file_size = request.POST.get("file_size")

    FileHistory.objects.create(
        user=request.user,
        organization=None,
        file_name=file_name,
        file_size=file_size,
        action="cancel",
        file_type="other",
        status="cancelled",
        failure_reason="CANCELLED",
        failure_message="User cancelled upload",
        ip_address=get_client_ip(request),
    )

    return JsonResponse({"success": True})

    

@login_required
def org_upload_page(request):
    org_member = request.user.org_membership
    org = request.user.org_membership.organization
    if org_member and org and org_member.can_upload and org_member.is_active and org.is_active:
        if request.method == 'GET':
            if request.user.is_superuser:
                base_template = "adminpanel/admin_base.html"
            else:
                base_template = "storageapp/base.html"

            # 👇 IMPORTANT PART
            recent_uploads = (
                FileHistory.objects
                .filter(user=request.user,organization=org)
                .order_by("-created_at")[:10]
            )

            return render(
                request,
                "storageapp/org-upload.html",
                {"recent_uploads": recent_uploads,
                "base_template": base_template},
            )
            
        if request.method == 'POST':
            file = request.FILES.get('file')

            if not file:
                return render(request, "storageapp/org-upload.html", {
                    "error": "Please select a file",
                    "base_template": base_template
                })
            
            used = (
                    CloudFile.objects
                    .filter(user=request.user, organization=org, is_deleted=False)
                    .aggregate(total=Sum("file_size"))["total"] or 0
                )

            
            if org_member.can_upload:
                if org:
                    limit = org.storage_limit
                    file_size_limit = org.file_size_lmt
                else:
                    limit = 0
                    file_size_limit = 0
            else:
                FileHistory.objects.create(
                        user=request.user,
                        organization=org,
                        file_name=file.name,
                        file_size=file.size,
                        file_type="other",
                        action="upload",
                        status="denied",
                        failure_reason="Permission_NOT_GIVEN",
                        failure_message="No permission to upload files. Contact organization admin.",
                        ip_address=get_client_ip(request),
                    )
                return JsonResponse({
                    "success": True,
                    "rejected_files": [{
                        "name": file.name,
                        "reason": "No permission to upload files. Contact organization admin."
                    }]
                })
            

            if limit is not None or file_size_limit is not None:
                if limit == 0 or file_size_limit == 0:
                    FileHistory.objects.create(
                        user=request.user,
                        organization=org,
                        file_name=file.name,
                        file_size=file.size,
                        file_type="other",
                        action="upload",
                        status="failed",
                        failure_reason="PLAN_ERROR",
                        failure_message="Error in Organization configure or storage. Contact organization admin.",
                        ip_address=get_client_ip(request),
                    )
                    return JsonResponse({
                        "success": True,
                        "rejected_files": [{
                            "name": file.name,
                            "reason": "Error in Organization configure or storage. Contact organization admin."
                        }]
                    })
                
                if limit is not None:
                    remaining_space = limit - used

                    if remaining_space <= 0:
                        FileHistory.objects.create(
                            user=request.user,
                            organization=org,
                            file_name=file.name,
                            file_size=file.size,
                            file_type="other",
                            action="upload",
                            status="failed",
                            failure_reason="STORAGE_FULL",
                            failure_message="Not enough storage. Upgrade storage.",
                            ip_address=get_client_ip(request),
                        )
                        return JsonResponse({
                            "success": True,
                            "rejected_files": [{
                                "name": file.name,
                                "reason": "Not enough storage. Upgrade storage."
                            }]
                        })
                
                
                    # 🚫 If this file does not fit, skip it
                    if file.size > remaining_space:
                        FileHistory.objects.create(
                            user=request.user,
                            organization=org,
                            file_name=file.name,
                            file_size=file.size,
                            file_type="other",
                            action="upload",
                            status="failed",
                            failure_reason="STORAGE_FULL",
                            failure_message="Not enough storage. Upgrade storage.",
                            ip_address=get_client_ip(request),
                        )
                        return JsonResponse({
                            "success": True,
                            "rejected_files": [{
                                "name": file.name,
                                "reason": "Not enough storage. Upgrade storage."
                            }]
                        })
                
                if file_size_limit is not None:
            
                    if file.size > file_size_limit:
                        FileHistory.objects.create(
                            user=request.user,
                            organization=org,
                            file_name=file.name,
                            file_size=file.size,
                            file_type="other",
                            action="upload",
                            status="failed",
                            failure_reason="FILE_TOO_LARGE",
                            failure_message=f"File Size Limit - {filesizeformat(file_size_limit)}.",
                            ip_address=get_client_ip(request),
                        )
                        return JsonResponse({
                            "success": True,
                            "rejected_files": [{
                                "name": file.name,
                                "reason": f"File Size Limit - {filesizeformat(file_size_limit)}."
                            }]
                        })


            mime_type, _ = mimetypes.guess_type(file.name)

            if mime_type and mime_type.startswith("image"):
                file_type = "image"
                folder = "images"
            
            elif mime_type and mime_type.startswith("video"):
                file_type = "video"
                folder = "videos"

            elif mime_type == "application/pdf":
                file_type = "document"
                folder = "pdfs"

            else:
                file_type = "other"
                folder = "documents"

            try:
                print("Uploading to S3...")
                file_url, s3_key = upload_to_s3(file, folder) 
                print("Upload success")

            except Exception as e:
                import traceback
                print("FULL ERROR:")
                traceback.print_exc()
                FileHistory.objects.create(
                    user=request.user,
                    organization=org,
                    file_name=file.name,
                    file_size=file.size,
                    file_type=file_type,
                    action="upload",
                    status="failed",
                    failure_reason="S3_UPLOAD_FAILED",
                    failure_message="Upload Failed at storage. Contact organization admin",
                    failure_comment=str(e),
                    ip_address=get_client_ip(request),
                )
                return JsonResponse({
                    "success": True,
                    "rejected_files": [{
                        "name": file.name,
                        "reason": "Upload Failed at storage. Contact organization admin"
                    }]
                })  

            CloudFile.objects.create(
                user=request.user,
                organization=org,
                file_name=file.name,
                file_size=file.size,
                file_type=file_type,
                file_url=generate_presigned_url(
                            s3_key,
                            filename=file.name
                        ),
                public_id=s3_key,
            )

            FileHistory.objects.create(
                user=request.user,
                organization=org,
                file_name=file.name,
                file_size=file.size,
                file_type=file_type,
                mime_type=mime_type,
                action="upload",
                status="success",
                file_url=file_url,
                public_id=s3_key,
                ip_address=get_client_ip(request),
            )

        return JsonResponse({
            "success": True,
            "uploaded_files": [file.name],
            "rejected_files": []
        })
    
    elif request.user.is_superuser:
        return redirect('storageapp:admin_dashboard')
    else:
        return redirect('storageapp:dashboard')
        
    



@require_POST
@login_required
def org_upload_cancelled(request):
    file_name = request.POST.get("file_name")
    file_size = request.POST.get("file_size")

    membership = request.user.org_membership
    if membership:
        org = membership.organization

    FileHistory.objects.create(
        user=request.user,
        organization=org,
        file_name=file_name,
        file_size=file_size,
        action="cancel",
        file_type="other",
        status="cancelled",
        failure_reason="CANCELLED",
        failure_message="User cancelled upload",
        ip_address=get_client_ip(request),
    )

    return JsonResponse({"success": True})



@login_required
def shared_files(request):
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
    


@require_POST
@login_required
def share_file_api(request, file_id):
    file = get_object_or_404(
        CloudFile,
        id=file_id,
        user=request.user,
        organization=None,
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

    # 🔍 Check if already shared
    if SharedFile.objects.filter(
        file=file,
        owner=request.user,
        shared_with=target_user
    ).exists():
        return JsonResponse({
            "success": False,
            "error": "File already shared with this user"
        })

    SharedFile.objects.get_or_create(
        file=file,
        owner=request.user,
        shared_with=target_user
    )

    return JsonResponse({"success": True})
    



@login_required
def myfiles(request):
    
    if request.user.is_superuser:
        base_template = "adminpanel/admin_base.html"
    else:
        base_template = "storageapp/base.html"

    q = request.GET.get("q", "").strip()
    file_type = request.GET.get("type")

    files = CloudFile.objects.filter(
        user=request.user,
        organization=None,
        is_deleted=False
    )

    # 🔹 Filter by category
    if file_type:
        files = files.filter(file_type=file_type)

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


@require_POST
@login_required
def move_to_trash(request, file_id):
    
    file = get_object_or_404(CloudFile, id=file_id, user=request.user, organization=None)
    file.is_deleted = True
    file.deleted_at = timezone.now()
    file.save()

    files = CloudFile.objects.filter(user=request.user, organization=None, is_deleted=False)

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
        organization=None,
        is_deleted=False
    ).filter(
        Q(user=request.user) |
        Q(shared_entries__shared_with=request.user)
    ).distinct().first()

    if not file:
        raise Http404("File not accessible")

    url = generate_presigned_url(
        file.public_id,
        download=True,
        filename=file.file_name
    )

    return redirect(url)


@login_required
def view_file(request, file_id):
    file = CloudFile.objects.filter(
        id=file_id,
        organization=None,
        is_deleted=False
    ).filter(
        Q(user=request.user) |
        Q(shared_entries__shared_with=request.user)
    ).distinct().first()

    if not file:
        raise Http404("File not accessible")

    # generate fresh temporary S3 link
    url = generate_presigned_url(file.public_id)

    return redirect(url)





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
def org_files(request):
    org_member = request.user.org_membership
    org = request.user.org_membership.organization
    if org_member and org and org_member.is_active and org.is_active:
        if request.user.is_superuser:
            base_template = "adminpanel/admin_base.html"
        else:
            base_template = "storageapp/base.html"

        q = request.GET.get("q", "").strip()
        file_type = request.GET.get("type")

        files = CloudFile.objects.filter(
            user=request.user,
            organization=org,
            is_deleted=False
        )

        # 🔹 Filter by category
        if file_type:
            files = files.filter(file_type=file_type)

        files = files.order_by("-uploaded_at")

        return render(
            request,
            "storageapp/org-files.html",
            {
                "files": files,
                "active_type": file_type,
                "base_template": base_template,
            }
        )
    elif request.user.is_superuser:
        return redirect('storageapp:admin_dashboard')
    else:
        return redirect('storageapp:dashboard')



@login_required
def trash(request):
    if request.user.is_superuser:
        base_template = "adminpanel/admin_base.html"
    else:
        base_template = "storageapp/base.html"

    files = CloudFile.objects.filter(
        user=request.user,
        organization=None,
        is_deleted=True
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
        "base_template": base_template,
    })



def trash_stats(user):
    files = CloudFile.objects.filter(user=user, organization=None, is_deleted=True)

    return {
        "count": files.count(),
        "size": sum(f.file_size for f in files),
        "expiring": sum(
            1 for f in files
            if f.days_left() is not None and f.days_left() <= 7
        )
    }



@login_required
def restore_file(request, file_id):
    file = get_object_or_404(
        CloudFile, id=file_id, organization=None, user=request.user, is_deleted=True
    )

    used = (
        CloudFile.objects
        .filter(user=request.user, organization=None, is_deleted=False)
        .aggregate(total=Sum("file_size"))["total"] or 0
    )

    sub = UserSubscription.objects.select_related("plan").filter(user=request.user).first()
    limit = sub.plan.storage_limit if sub and sub.plan else 0

    if limit:
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
        .filter(user=user, organization=None, is_deleted=False)
        .aggregate(total=Sum("file_size"))["total"] or 0
    )

    # 2️⃣ Total size of deleted files
    deleted_total = (
        CloudFile.objects
        .filter(user=user, organization=None, is_deleted=True)
        .aggregate(total=Sum("file_size"))["total"] or 0
    )

    # 3️⃣ Get storage limit
    sub = UserSubscription.objects.select_related("plan").filter(user=user).first()
    limit = sub.plan.storage_limit if sub and sub.plan else 0

    if limit:
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
        CloudFile,
        id=file_id,
        user=request.user,
        organization=None,
        is_deleted=True
    )

    # delete from S3
    try:
        delete_from_s3(file.public_id)
        # delete from DB
        file.delete()
    except Exception:
        pass  # optional: log error

    

    return JsonResponse({
        "success": True,
        "stats": trash_stats(request.user)
    })


@login_required
def empty_trash(request):
    files = CloudFile.objects.filter(
        user=request.user,
        organization=None,
        is_deleted=True
    )

    for file in files:
        try:
            delete_from_s3(file.public_id)
            file.delete()
        except Exception:
            pass  # optional: log error

    

    return JsonResponse({
        "success": True,
        "message": "Trash emptied successfully"
    })




def settings_page(request):

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
            profile_file = request.FILES.get("profile_picture")
            if user.profile_picture:
                user.profile_picture.delete(save=False)
            user.profile_picture = profile_file

        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.email = request.POST.get("email", user.email)
        user.phone = request.POST.get("phone", user.phone)

        user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("storageapp:settings_page")

    profile_image_url = None

    if user.profile_picture:
        try:
            profile_image_url = generate_presigned_url(
                user.profile_picture.name,
            )
        except Exception:
            profile_image_url = None

    return render(
        request,
        "storageapp/settings.html",
        {
            "base_template": base_template,
            "profile_image_url": profile_image_url,
        },
    )
    
    

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


    



def run_daily_cleanup():
    key = "daily_trash_cleanup"
    if not cache.get(key):
        cleanup_trash()
        cache.set(key, True, 60 * 60 * 24)  # 24 hours


def set_timezone(request):
    if request.method == "POST":
        tz = request.POST.get("timezone")
        if tz:
            request.session["user_timezone"] = tz
        return JsonResponse({"success": True})
    

def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0]
    return request.META.get("REMOTE_ADDR")