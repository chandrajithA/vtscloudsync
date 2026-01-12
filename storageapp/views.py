from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import *
import os
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

User = get_user_model()



@login_required
def dashboard(request):
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
def upload_page(request):
    if request.method == 'GET':
        # 👇 IMPORTANT PART
        last_uploads = (
            CloudFile.objects
            .filter(user=request.user)
            .order_by("-uploaded_at")[:10]
        )

        return render(
            request,
            "storageapp/upload.html",
            {"last_uploads": last_uploads},
        )
        
    if request.method == 'POST':
        files = request.FILES.getlist('file')

        if not files:
            return render(request, "storageapp/upload.html", {
                "error": "Please select a file"
            })
    
        
        for file in files:
        
            mime_type, _ = mimetypes.guess_type(file.name)
            name, ext = os.path.splitext(file.name)

            uploaded_file = None
            file_url = None
            public_id = None

            if mime_type and mime_type.startswith("image"):
                file_type = "image"
                result = cloudinary.uploader.upload(
                    file,
                    folder="images",
                    use_filename=True,
                    unique_filename=False,
                    resource_type="image"
                )
                file_url = result["secure_url"]
                public_id = result["public_id"]
                resource_type="image"

            # ✅ VIDEO
            elif mime_type and mime_type.startswith("video"):
                file_type = "video"
                result = cloudinary.uploader.upload(
                    file,
                    resource_type="raw",
                    folder="videos",
                    use_filename=True,
                    unique_filename=False,
                )
                file_url = result["secure_url"]
                public_id = result["public_id"]

            # ✅ PDF
            elif mime_type == "application/pdf":
                file_type = "document"
                result = cloudinary.uploader.upload(
                    file,
                    resource_type="raw",
                    folder="PDFs",
                    use_filename=True,
                    unique_filename=False,
                )
                file_url = result["secure_url"]
                public_id = result["public_id"]

            # ✅ OTHER FILES
            else:
                file_type = "other"
                result = cloudinary.uploader.upload(
                    file,
                    resource_type="raw",
                    folder="documents",
                    use_filename=True,
                    unique_filename=False,
                )
                file_url = result["secure_url"]
                public_id = result["public_id"]

            CloudFile.objects.create(
                user=request.user,
                file_name=file.name,
                file_size=file.size,
                file_type=file_type,
                uploaded_file=uploaded_file,
                file_url=file_url,
                public_id=public_id,
            )

        return JsonResponse({"success": True})
    





@login_required
def shared_files(request):
    shared_with_me = SharedFile.objects.filter(
        shared_with=request.user,
        file__is_deleted=False
    ).select_related("file", "owner")

    shared_by_me = SharedFile.objects.filter(
        owner=request.user,
        file__is_deleted=False
    ).select_related("file", "shared_with")

    return render(request, "storageapp/shared.html", {
        "shared_with_me": shared_with_me,
        "shared_by_me": shared_by_me,
    })


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




@login_required
def myfiles(request):
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
        }
    )





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
    if request.user != shared.owner and request.user != shared.shared_with:
        return JsonResponse({"success": False, "error": "Not allowed"})

    # ✅ ONLY remove share entry
    shared.delete()

    return JsonResponse({"success": True})





@login_required
def myfiles_search(request):
    q = request.GET.get("q", "").strip()

    files = CloudFile.objects.filter(
        user=request.user,
        is_deleted=False,
        file_name__icontains=q
    ) if q else CloudFile.objects.none()

    return render(
        request,
        "storageapp/partials/myfiles_list.html",
        {"files": files}
    )




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

@login_required
def trash(request):
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
    })

@login_required
def restore_file(request, file_id):
    file = get_object_or_404(
        CloudFile, id=file_id, user=request.user, is_deleted=True
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
    CloudFile.objects.filter(user=request.user, is_deleted=True)\
        .update(is_deleted=False, deleted_at=None)
    return JsonResponse({"success": True})


@login_required
def delete_file(request, file_id):
    file = get_object_or_404(
        CloudFile, id=file_id, user=request.user, is_deleted=True
    )

    # delete from cloudinary
    cloudinary.uploader.destroy(
        file.public_id,
        resource_type="raw" if file.file_type in ["document", "other", "video"] else file.file_type
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
            resource_type="raw" if file.file_type in ["document", "other", "video"] else file.file_type
        )

    files.delete()
    return JsonResponse({"success": True})



@login_required
def settings(request):
    # files = File.objects.filter(owner=request.user, is_deleted=False)
    return render(request, 'storageapp/settings.html')



