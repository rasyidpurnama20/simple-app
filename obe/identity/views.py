from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetConfirmView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from obe.identity.models import MFAChallenge
from obe.identity.services import (
    account_security,
    issue_mfa_challenge,
    register_login_failure,
    register_login_success,
    verify_mfa_challenge,
)
from obe.shared.services import ActorContext, record_change


def _remote_ip(request) -> str | None:
    value = request.META.get("REMOTE_ADDR", "")
    return value or None


def _audit_auth(request, user, action: str, outcome: str) -> None:
    record_change(
        actor=ActorContext(
            str(user.pk),
            user.get_username(),
            correlation_id=request.correlation_id,
        ),
        action=action,
        object_type="user",
        object_id=str(user.pk),
        summary=f"Authentication {outcome}",
        ip_address=_remote_ip(request),
        user_agent=request.headers.get("User-Agent", ""),
        outcome=outcome,
    )


class SecureLoginView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        user = form.get_user()
        try:
            profile = register_login_success(user, ip_address=_remote_ip(self.request))
        except PermissionDenied:
            self._locked_rejection = True
            form.add_error(None, "Akun tidak dapat digunakan saat ini.")
            _audit_auth(self.request, user, "identity.login", "locked")
            return self.form_invalid(form)
        response = super().form_valid(form)
        self.request.session["obe_permission_epoch"] = profile.permission_epoch
        _audit_auth(self.request, user, "identity.login", "success")
        if profile.mfa_enabled:
            if not user.email:
                logout(self.request)
                form.add_error(None, "Akun MFA belum memiliki kanal verifikasi.")
                return self.form_invalid(form)
            challenge, token = issue_mfa_challenge(user)
            send_mail(
                "Kode verifikasi OBE Apps",
                f"Kode verifikasi sekali pakai Anda: {token}",
                None,
                [user.email],
                fail_silently=False,
            )
            self.request.session["obe_mfa_challenge"] = challenge.pk
            self.request.session["obe_mfa_verified"] = False
            return HttpResponseRedirect(reverse("mfa-verify"))
        self.request.session["obe_mfa_verified"] = True
        return response

    def form_invalid(self, form):
        username = str(self.request.POST.get("username", ""))[:150]
        User = get_user_model()
        user = User.objects.filter(username__iexact=username).first()
        if user is not None and not getattr(self, "_locked_rejection", False):
            register_login_failure(user, ip_address=_remote_ip(self.request))
            _audit_auth(self.request, user, "identity.login", "denied")
        return super().form_invalid(form)


class AuditedLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            _audit_auth(request, request.user, "identity.logout", "success")
        return super().post(request, *args, **kwargs)


class SecurePasswordResetConfirmView(PasswordResetConfirmView):
    def form_valid(self, form):
        response = super().form_valid(form)
        profile = account_security(self.user)
        profile.password_reset_required = False
        profile.failed_attempts = 0
        profile.locked_until = None
        profile.permission_epoch += 1
        profile.save(
            update_fields=[
                "password_reset_required",
                "failed_attempts",
                "locked_until",
                "permission_epoch",
                "updated_at",
            ]
        )
        record_change(
            actor=ActorContext(str(self.user.pk), self.user.get_username()),
            action="identity.credential.reset",
            object_type="user",
            object_id=str(self.user.pk),
            summary="Credential reset completed",
            outcome="success",
        )
        return response


@require_http_methods(["GET", "POST"])
def verify_mfa(request):
    if not request.user.is_authenticated:
        return redirect("login")
    challenge_id = request.session.get("obe_mfa_challenge")
    if not challenge_id:
        return redirect("dashboard")
    if request.method == "POST":
        token = str(request.POST.get("token", ""))
        try:
            valid = verify_mfa_challenge(challenge_id, token, user=request.user)
        except (MFAChallenge.DoesNotExist, ValidationError, ValueError):
            valid = False
        if valid:
            request.session["obe_mfa_verified"] = True
            request.session.pop("obe_mfa_challenge", None)
            _audit_auth(request, request.user, "identity.mfa", "success")
            return redirect("dashboard")
        messages.error(request, "Kode verifikasi tidak valid atau kedaluwarsa.")
        _audit_auth(request, request.user, "identity.mfa", "denied")
    return render(request, "registration/mfa_verify.html")
