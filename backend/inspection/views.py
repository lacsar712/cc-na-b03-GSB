from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from inspection.models import FilterPreset, Inspection
from inspection.rules import VERDICTS, judge

SESSION_PRESET_KEY = "active_preset_id"


def _can_write(user) -> bool:
    return user.groups.filter(name="inspector").exists()


def health(_request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok", "service": "nav-aid-inspection"})


@require_http_methods(["GET", "POST"])
def login_view(request):
    from django.contrib.auth import authenticate, login

    error = ""
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user is None:
            error = "用户名或密码错误"
        else:
            login(request, user)
            return redirect("list")
    return render(request, "login.html", {"error": error})


def logout_view(request):
    from django.contrib.auth import logout

    logout(request)
    return redirect("login")


def _active_preset(request):
    """当前套用的方案；方案被删后自动回到全部。"""
    preset_id = request.session.get(SESSION_PRESET_KEY)
    if preset_id is None:
        return None
    preset = FilterPreset.objects.filter(pk=preset_id).first()
    if preset is None:
        request.session.pop(SESSION_PRESET_KEY, None)
    return preset


@login_required
def list_view(request):
    if "apply" in request.GET:
        try:
            preset_id = int(request.GET["apply"])
        except (TypeError, ValueError):
            preset_id = None
        if FilterPreset.objects.filter(pk=preset_id).exists():
            request.session[SESSION_PRESET_KEY] = preset_id
        return redirect("list")
    if "clear" in request.GET:
        request.session.pop(SESSION_PRESET_KEY, None)
        return redirect("list")

    active = _active_preset(request)
    rows = Inspection.objects.all()
    if active is not None:
        if active.verdicts:
            rows = rows.filter(verdict__in=active.verdicts)
        if active.code_contains:
            rows = rows.filter(aid_code__icontains=active.code_contains)
    return render(
        request,
        "list.html",
        {
            "rows": rows,
            "can_write": _can_write(request.user),
            "presets": FilterPreset.objects.all(),
            "active_preset": active,
            "verdict_choices": VERDICTS,
        },
    )


@login_required
@require_http_methods(["POST"])
def preset_create_view(request):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅巡检员可维护查找方案")
    name = request.POST.get("name", "").strip()
    verdicts = [v for v in request.POST.getlist("verdicts") if v in VERDICTS]
    code_contains = request.POST.get("code_contains", "").strip()
    if not name:
        messages.error(request, "方案名不能为空")
    elif FilterPreset.objects.filter(name=name).exists():
        messages.error(request, f"方案名「{name}」已存在")
    elif not verdicts:
        messages.error(request, "至少勾选一个判词")
    else:
        FilterPreset.objects.create(
            name=name,
            verdicts=verdicts,
            code_contains=code_contains,
            created_by=request.user.username,
        )
        messages.success(request, f"已保存方案「{name}」，点「套用」即可收窄总表")
    return redirect("list")


@login_required
@require_http_methods(["POST"])
def preset_rename_view(request, pk):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅巡检员可维护查找方案")
    preset = get_object_or_404(FilterPreset, pk=pk)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "方案名不能为空")
    elif FilterPreset.objects.filter(name=name).exclude(pk=preset.pk).exists():
        messages.error(request, f"方案名「{name}」已存在")
    else:
        preset.name = name
        preset.save(update_fields=["name"])
        messages.success(request, f"已改名为「{name}」")
    return redirect("list")


@login_required
@require_http_methods(["POST"])
def preset_delete_view(request, pk):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅巡检员可维护查找方案")
    preset = get_object_or_404(FilterPreset, pk=pk)
    name = preset.name
    preset.delete()
    if request.session.get(SESSION_PRESET_KEY) == pk:
        request.session.pop(SESSION_PRESET_KEY, None)
    messages.success(request, f"已删除方案「{name}」，总表恢复显示全部")
    return redirect("list")


@login_required
def detail_view(request, pk):
    row = get_object_or_404(Inspection, pk=pk)
    return render(request, "detail.html", {"row": row})


@login_required
@require_http_methods(["GET", "POST"])
def create_view(request):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅巡检员可登记灯光巡检")
    error = ""
    if request.method == "POST":
        try:
            measured = float(request.POST["measured_cd"])
            required = float(request.POST["required_cd"])
            bearing = float(request.POST["bearing_error_deg"])
            code = request.POST["aid_code"].strip()
            if not code:
                raise ValueError("empty")
        except (KeyError, ValueError):
            error = "请填编号和三项数值"
        else:
            verdict, note = judge(measured, required, bearing)
            row = Inspection.objects.create(
                aid_code=code,
                measured_cd=measured,
                required_cd=required,
                bearing_error_deg=bearing,
                verdict=verdict,
                note=note,
                created_by=request.user.username,
            )
            return redirect("detail", pk=row.pk)
    return render(request, "form.html", {"error": error})
