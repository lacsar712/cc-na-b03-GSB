from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from inspection.models import FilterScheme, Inspection
from inspection.rules import judge

ACTIVE_SCHEME_KEY = "active_scheme_id"
VERDICT_CHOICES = ["合格", "不合格"]


def _can_write(user) -> bool:
    return user.groups.filter(name="inspector").exists()


def _get_active_scheme(request):
    """返回当前套用的方案；session 里是已删方案的残留 id 时清掉。"""
    scheme_id = request.session.get(ACTIVE_SCHEME_KEY)
    if scheme_id is None:
        return None
    scheme = FilterScheme.objects.filter(pk=scheme_id).first()
    if scheme is None:
        request.session.pop(ACTIVE_SCHEME_KEY, None)
    return scheme


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


@login_required
def list_view(request):
    active_scheme = _get_active_scheme(request)
    if active_scheme is None:
        rows = Inspection.objects.all()
    else:
        rows = active_scheme.matches()
    return render(
        request,
        "list.html",
        {
            "rows": rows,
            "schemes": FilterScheme.objects.all(),
            "active_scheme": active_scheme,
            "verdict_choices": VERDICT_CHOICES,
        },
    )


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


@login_required
@require_POST
def scheme_apply_view(request, pk):
    scheme = get_object_or_404(FilterScheme, pk=pk)
    request.session[ACTIVE_SCHEME_KEY] = scheme.pk
    return redirect("list")


@login_required
@require_POST
def scheme_clear_view(request):
    request.session.pop(ACTIVE_SCHEME_KEY, None)
    return redirect("list")


def _parse_scheme_form(request):
    name = request.POST.get("name", "").strip()
    chosen = []
    for value in request.POST.getlist("verdicts"):
        if value in VERDICT_CHOICES and value not in chosen:
            chosen.append(value)
    aid_text = request.POST.get("aid_text", "").strip()
    return name, chosen, aid_text


@login_required
@require_POST
def scheme_create_view(request):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅持灯账号可新建查找方案")
    name, chosen, aid_text = _parse_scheme_form(request)
    if not name:
        messages.error(request, "方案名称不能为空")
    elif not chosen and not aid_text:
        messages.error(request, "请至少勾选一个判词或填写一段灯号文字")
    elif FilterScheme.objects.filter(name=name).exists():
        messages.error(request, "方案名称已存在")
    else:
        FilterScheme.objects.create(
            name=name,
            verdicts=",".join(chosen),
            aid_text=aid_text,
            created_by=request.user.username,
        )
    return redirect("list")


@login_required
@require_POST
def scheme_rename_view(request, pk):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅持灯账号可改名查找方案")
    scheme = get_object_or_404(FilterScheme, pk=pk)
    new_name = request.POST.get("name", "").strip()
    if not new_name:
        messages.error(request, "方案名称不能为空")
    elif FilterScheme.objects.filter(name=new_name).exclude(pk=scheme.pk).exists():
        messages.error(request, "方案名称已存在")
    else:
        scheme.name = new_name
        scheme.save(update_fields=["name"])
    return redirect("list")


@login_required
@require_POST
def scheme_delete_view(request, pk):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅持灯账号可删除查找方案")
    scheme = get_object_or_404(FilterScheme, pk=pk)
    was_active = request.session.get(ACTIVE_SCHEME_KEY) == scheme.pk
    scheme.delete()
    if was_active:
        # 删除正套用的方案后，总表恢复可看全部
        request.session.pop(ACTIVE_SCHEME_KEY, None)
    return redirect("list")
