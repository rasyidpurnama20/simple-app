"""Timeline_Engine validators.

Builds plain-language ``DomainError`` instances (problem + corrective step,
free of internal-system terminology) for the Timeline_Engine's business rules
(Requirements 14.2, 14.3). All error construction goes through
``core.validators.build_domain_error`` so messages are guaranteed
jargon-free.
"""

from __future__ import annotations

from core.exceptions import DomainError
from core.validators import build_domain_error


def error_template_without_phase(template_name: str) -> DomainError:
    """Reject instantiating a template that has no phase (Requirement 1.5)."""
    return build_domain_error(
        problem=(
            f"Template linimasa \u201c{template_name}\u201d belum memiliki satu pun "
            "tahap, sehingga siklus tidak dapat dibuat."
        ),
        corrective_step=(
            "Tambahkan minimal satu tahap beserta milestone dan tugasnya pada "
            "template sebelum membuat siklus."
        ),
    )


def error_hard_dependency_blocks(predecessor_titles: list[str]) -> DomainError:
    """Reject starting work while a hard dependency is incomplete (Req 3.2)."""
    names = ", ".join(f"\u201c{title}\u201d" for title in predecessor_titles)
    return build_domain_error(
        problem=(
            "Tugas ini belum dapat dikerjakan karena pekerjaan pendahulu yang "
            f"wajib selesai masih berjalan: {names}."
        ),
        corrective_step=(
            "Selesaikan terlebih dahulu pekerjaan pendahulu tersebut, lalu mulai "
            "tugas ini kembali."
        ),
    )


def error_checklist_incomplete(open_items: list[str]) -> DomainError:
    """Reject completing a task with open checklist items (Requirement 2.7)."""
    names = ", ".join(f"\u201c{item}\u201d" for item in open_items)
    return build_domain_error(
        problem=(
            "Tugas belum dapat ditandai selesai karena masih ada butir "
            f"daftar periksa yang belum tuntas: {names}."
        ),
        corrective_step=(
            "Tuntaskan seluruh butir daftar periksa, kemudian tandai tugas "
            "sebagai selesai."
        ),
    )


def error_reason_required() -> DomainError:
    """Reject a schedule change without a reason (Requirement 5.2)."""
    return build_domain_error(
        problem="Perubahan jadwal belum menyertakan alasan.",
        corrective_step=(
            "Tuliskan alasan perubahan jadwal agar riwayat tetap dapat ditelusuri."
        ),
    )


def error_invalid_submit_state(current_label: str) -> DomainError:
    """Reject returning a task for revision when it is not under review."""
    return build_domain_error(
        problem=(
            "Tugas hanya dapat dikembalikan untuk revisi setelah diajukan untuk "
            f"ditinjau, sedangkan status saat ini adalah \u201c{current_label}\u201d."
        ),
        corrective_step=(
            "Minta pemilik tugas mengajukan tugas terlebih dahulu, lalu kembalikan "
            "untuk revisi bila diperlukan."
        ),
    )
