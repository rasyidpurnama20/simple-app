from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .roles import role_for_user


def home(request):
    return redirect("dashboard" if request.user.is_authenticated else "login")


def healthz(request):
    return JsonResponse({"status": "ok", "stage": 0})


@login_required
def dashboard(request):
    return render(request, "dashboard.html", {"role": role_for_user(request.user)})
