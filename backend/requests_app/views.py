from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import CommentForm, ServiceRequestForm
from .models import ServiceRequest
from .selectors import service_request_filter, service_request_get
from .services import (
    comment_create,
    service_request_create,
    service_request_update,
)
from django.http import Http404, HttpResponseForbidden
from .workflow_forms import AssignmentForm, ResolutionForm
from .services import service_request_assign, service_request_resolve
from .selectors import service_request_summary


@login_required
def request_list(request):
    queryset = service_request_filter(
        user=request.user,
        status=request.GET.get("status", ""),
        query=request.GET.get("q", ""),
    )

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "requests_app/request_list.html", {
        "page_obj": page_obj,
        "requests": page_obj,
        "status": request.GET.get("status", ""),
        "q": request.GET.get("q", ""),
        "status_choices": ServiceRequest.Status.choices,
        "summary": service_request_summary(user=request.user),
        "query_params": query_params.urlencode(),
    })


@login_required
def request_detail(request, request_id):
    try:
        item = service_request_get(
            user=request.user,
            request_id=request_id,
        )
    except ServiceRequest.DoesNotExist:
        raise Http404

    comments = item.comments.select_related("author").order_by("created_at")

    return render(request, "requests_app/request_detail.html", {
        "item": item,
        "comments": comments,
        "comment_form": CommentForm(),
        "assignment_form": AssignmentForm(),
        "resolution_form": ResolutionForm(),
    })


@login_required
def request_create(request):
    form = ServiceRequestForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        item = service_request_create(
            requester=request.user,
            **form.cleaned_data,
        )
        messages.success(request, "Request created successfully.")
        return redirect("requests:detail", request_id=item.id)

    return render(request, "requests_app/request_form.html", {
        "form": form,
        "page_title": "Create Service Request",
    })


@login_required
def request_update(request, request_id):
    try:
        item = service_request_get(
            user=request.user,
            request_id=request_id,
        )
    except ServiceRequest.DoesNotExist:
        raise Http404

    form = ServiceRequestForm(
        request.POST or None,
        instance=item,
    )

    if request.method == "POST" and form.is_valid():
        try:
            updated_item = service_request_update(
                item=item,
                actor=request.user,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Request updated successfully.")
            return redirect(
                "requests:detail",
                request_id=updated_item.id,
            )

    return render(request, "requests_app/request_form.html", {
        "form": form,
        "page_title": "Update Service Request",
    })


@require_POST
@login_required
def comment_add(request, request_id):
    try:
        item = service_request_get(
            user=request.user,
            request_id=request_id,
        )
    except ServiceRequest.DoesNotExist:
        raise Http404

    form = CommentForm(request.POST)

    if form.is_valid():
        comment_create(
            item=item,
            author=request.user,
            **form.cleaned_data,
        )
        messages.success(request, "Comment added.")
    else:
        messages.error(request, "Please enter a valid comment.")

    return redirect("requests:detail", request_id=item.id)


@require_POST
@login_required
def request_assign(request, request_id):
    if not request.user.is_staff:
        return HttpResponseForbidden()

    try:
        item = service_request_get(user=request.user, request_id=request_id)
    except ServiceRequest.DoesNotExist:
        raise Http404

    form = AssignmentForm(request.POST)

    if form.is_valid():
        try:
            service_request_assign(
                item=item,
                technician=form.cleaned_data["technician"],
                actor=request.user,
            )
            messages.success(request, "Technician assigned successfully.")
        except ValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Please select a valid technician.")

    return redirect("requests:detail", request_id=item.id)


@require_POST
@login_required
def request_resolve(request, request_id):
    try:
        item = service_request_get(user=request.user, request_id=request_id)
    except ServiceRequest.DoesNotExist:
        raise Http404

    if not (
        request.user.is_staff
        or (
            hasattr(item, "work_order")
            and item.work_order.technician == request.user
        )
    ):
        return HttpResponseForbidden()

    form = ResolutionForm(request.POST)

    if form.is_valid():
        try:
            service_request_resolve(
                item=item,
                actor=request.user,
                **form.cleaned_data,
            )
            messages.success(request, "Request resolved successfully.")
        except ValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Please enter valid work notes.")

    return redirect("requests:detail", request_id=item.id)