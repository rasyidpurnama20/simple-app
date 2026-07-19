from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


def healthz(_request):
    return JsonResponse({"status": "ok"})


def readyz(_request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ready"})


@login_required
def dashboard(request):
    cards = [
        ("Kurikulum", "5 PL · 12 CPL · 31 CPMK", "Pemetaan dan versi kurikulum"),
        ("Pembelajaran", "RPS & 16 minggu", "Rencana, realisasi, dan kehadiran"),
        ("Asesmen", "Bobot tervalidasi", "Rubrik, nilai, dan attainment"),
        ("Mutu", "PPEPP & CQI", "Finding, tindakan, dan bukti"),
    ]
    return render(request, "dashboard.html", {"cards": cards})
