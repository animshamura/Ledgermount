import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from src.domains.ledger.models.journal import Account, LedgerEntry
from src.domains.webhooks.models.outbox import WebhookOutbox

logger = logging.getLogger("ledger.services")

class LedgerTransferService:
    @staticmethod
    def execute_transfer(debit_account_id: str, credit_account_id: str, amount: int, idempotency_key: str) -> LedgerEntry:
        if amount <= 0:
            raise ValidationError("Transfer amount must be greater than zero.")
        if not idempotency_key or not idempotency_key.strip():
            raise ValidationError("Idempotency key is required.")

        requested_source = str(debit_account_id)
        requested_destination = str(credit_account_id)
        existing_entry = LedgerEntry.objects.filter(idempotency_key=idempotency_key).select_related(
            "debit_account", "credit_account"
        ).first()
        if existing_entry:
            if (
                str(existing_entry.debit_account_id) != requested_source
                or str(existing_entry.credit_account_id) != requested_destination
                or existing_entry.amount != amount
            ):
                raise ValidationError("Idempotency key was already used for a different transfer.")
            return existing_entry

        account_ids = sorted([str(debit_account_id), str(credit_account_id)])

        with transaction.atomic():
            locked_accounts = {
                str(acc.id): acc for acc in Account.objects.select_for_update().filter(id__in=account_ids)
            }
            source_acc = locked_accounts.get(str(debit_account_id))
            destination_acc = locked_accounts.get(str(credit_account_id))

            if not source_acc or not destination_acc:
                raise ValidationError("One or both specified accounts do not exist.")
            if source_acc.id == destination_acc.id:
                raise ValidationError("Source and destination accounts must differ.")
            if source_acc.is_frozen:
                raise ValidationError("The source account is frozen.")
            if destination_acc.is_frozen:
                raise ValidationError("The destination account is frozen.")
            if source_acc.currency != destination_acc.currency:
                raise ValidationError("Source and destination accounts must use the same currency.")
            if source_acc.balance < amount:
                raise ValidationError("Insufficient funds.")

            source_acc.balance -= amount
            destination_acc.balance += amount
            source_acc.save(update_fields=['balance', 'updated_at'])
            destination_acc.save(update_fields=['balance', 'updated_at'])

            ledger_entry = LedgerEntry.objects.create(
                idempotency_key=idempotency_key,
                debit_account=source_acc,
                credit_account=destination_acc,
                amount=amount,
                description=f"Transfer {amount} from {source_acc.id} to {destination_acc.id}"
            )

            WebhookOutbox.objects.create(
                event_type="ledger.transfer.completed",
                payload={
                    "ledger_entry_id": str(ledger_entry.id),
                    "amount": amount,
                    "timestamp": ledger_entry.created_at.isoformat()
                }
            )

            transaction.on_commit(LedgerTransferService._enqueue_webhook_outbox)
            return ledger_entry

    @staticmethod
    def _enqueue_webhook_outbox() -> None:
        try:
            from src.domains.webhooks.tasks import process_outbox_queue
            process_outbox_queue.delay()
        except Exception:
            logger.exception("Unable to enqueue webhook outbox processing")
