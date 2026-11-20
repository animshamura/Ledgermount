from src.domains.ledger.models.journal import AuditLog


def record_audit(actor_username, action, *, success=True, object_type="", object_id="", metadata=None, request=None):
    ip_address = None
    if request is not None:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = (forwarded.split(",", 1)[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None

    return AuditLog.objects.create(
        actor_username=actor_username or "",
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        success=success,
        metadata=metadata or {},
        ip_address=ip_address,
    )
