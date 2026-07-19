from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from obe.academic_lifecycle.models import Notification, TaskInstance
from obe.secure_exam.services import is_participant_in_active_exam

REMINDER_OFFSETS = (14, 7, 3, 1, 0, -1, -3, -7)


@shared_task
def schedule_task_reminders() -> int:
    now = timezone.now()
    created = 0
    for task in TaskInstance.objects.exclude(status__in=["completed", "cancelled", "waived"]):
        if is_participant_in_active_exam(str(task.owner_id)):
            continue
        for days in REMINDER_OFFSETS:
            scheduled = task.due_at - timedelta(days=days)
            if not now <= scheduled < now + timedelta(minutes=15):
                continue
            _, was_created = Notification.objects.get_or_create(
                recipient=task.owner,
                task=task,
                idempotency_key=f"task:{task.public_id}:T{days:+d}",
                defaults={
                    "title": task.title,
                    "body": f"Tugas {task.code} jatuh tempo {task.due_at:%d-%m-%Y %H:%M}",
                    "scheduled_at": scheduled,
                },
            )
            created += int(was_created)
    return created
