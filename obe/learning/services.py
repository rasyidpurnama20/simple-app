from decimal import Decimal

from obe.learning.models import Attendance, RPSVersion


def attendance_eligibility(*, offering_id: int, student_id: str) -> dict:
    rows = Attendance.objects.filter(offering_id=offering_id, student_id=student_id)
    counted = rows.exclude(status__in=["cancelled", "exempt"])
    denominator = counted.count()
    attended = counted.filter(status__in=["present", "late", "permit", "sick"]).count()
    percent = Decimal("0") if denominator == 0 else Decimal(attended * 100) / denominator
    return {
        "eligible": denominator > 0 and percent >= Decimal("75"),
        "percent": percent.quantize(Decimal("0.01")),
        "attended": attended,
        "denominator": denominator,
        "reason_code": "ATTENDANCE_OK" if percent >= 75 else "ATTENDANCE_BELOW_75",
    }


def publish_rps(rps: RPSVersion) -> RPSVersion:
    rps.status = RPSVersion.Status.PUBLISHED
    rps.full_clean()
    rps.approval_snapshot = {
        "version": rps.version,
        "reviewer": rps.reviewed_by_id,
        "approver": rps.approved_by_id,
        "weight": str(rps.total_assessment_weight),
    }
    rps.save(update_fields=["status", "approval_snapshot", "updated_at"])
    return rps
