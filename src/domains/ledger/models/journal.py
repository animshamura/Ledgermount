import uuid
from django.db import models
from django.core.exceptions import ValidationError

class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True, unique=True)
    balance = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=255, unique=True, db_index=True)
    debit_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="debits")
    credit_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="credits")
    amount = models.BigIntegerField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Amount must be strictly positive.")
        if self.debit_account_id == self.credit_account_id:
            raise ValidationError("Debit and Credit accounts cannot be identical.")

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_username = models.CharField(max_length=150, blank=True, default="")
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=100, blank=True, default="")
    object_id = models.CharField(max_length=255, blank=True, default="")
    success = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
