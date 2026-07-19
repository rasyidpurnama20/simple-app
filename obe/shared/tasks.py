from celery import current_app, shared_task
from django.db import transaction
from django.utils import timezone

from obe.shared.models import OutboxEvent


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=5)
def publish_outbox(self, batch_size: int = 100) -> int:
    published = 0
    with transaction.atomic():
        events = list(
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(published_at__isnull=True, attempts__lt=5)
            .order_by("occurred_at")[:batch_size]
        )
        for event in events:
            current_app.send_task(
                event.event_type,
                kwargs={"event_id": str(event.event_id), "payload": event.payload},
                headers={"correlation_id": str(event.correlation_id)},
            )
            event.published_at = timezone.now()
            event.attempts += 1
            event.save(update_fields=["published_at", "attempts"])
            published += 1
    return published
