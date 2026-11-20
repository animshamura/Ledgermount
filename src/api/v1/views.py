from django.contrib.auth import authenticate, get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAdminUser, BasePermission
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from src.domains.ledger.services.transfer import LedgerTransferService
from src.domains.ledger.models.journal import Account, AuditLog, LedgerEntry
from .serializers import (
    AccountSerializer,
    AccountCreateSerializer,
    LedgerEntrySerializer,
    TransferRequestSerializer,
    StaffAccountSerializer,
    WebhookEventSerializer,
    AuditLogSerializer,
)
from src.domains.ledger.services.audit import record_audit
from src.domains.webhooks.models.outbox import WebhookOutbox
from django.db.models import Count, Sum
from django.utils import timezone


class LedgerTransferView(APIView):
    def post(self, request, *args, **kwargs):
        idempotency_key = request.headers.get("X-Idempotency-Key")

        if not idempotency_key:
            return Response({"error": "Header missing: X-Idempotency-Key"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TransferRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        transfer = serializer.validated_data

        try:
            ledger_entry = LedgerTransferService.execute_transfer(
                debit_account_id=str(transfer['source_account_id']),
                credit_account_id=str(transfer['destination_account_id']),
                amount=transfer['amount'],
                idempotency_key=idempotency_key
            )
            record_audit(request.user.username, "transfer_execute", success=True, object_type="LedgerEntry", object_id=ledger_entry.id, metadata={"source_account_id": str(transfer['source_account_id']), "destination_account_id": str(transfer['destination_account_id']), "amount": transfer['amount']}, request=request)
            return Response({
                "transaction_id": str(ledger_entry.id),
                "status": "AUTHORIZED",
                "message": "Funds successfully captured and settled globally."
            }, status=status.HTTP_201_CREATED)
        except (ValidationError, DjangoValidationError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Critical system exception: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class StaffTokenView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "staff_login"

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_staff:
            record_audit(username or "", "staff_login", success=False, object_type="StaffAccount", request=request)
            return Response({"error": "Invalid staff credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)
        record_audit(user.username, "staff_login", success=True, object_type="StaffAccount", object_id=user.pk, request=request)
        return Response({"token": token.key, "is_superuser": user.is_superuser}, status=status.HTTP_200_OK)


class StaffLogoutView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        username = request.user.username
        request.auth.delete()
        record_audit(username, "staff_logout", success=True, object_type="StaffAccount", object_id=request.user.pk, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountListView(generics.ListAPIView):
    serializer_class = AccountSerializer

    def get_queryset(self):
        from django.db.models import Q
        queryset = Account.objects.all()
        search = (self.request.query_params.get('search') or '').strip()
        currency = (self.request.query_params.get('currency') or '').strip().upper()
        if search:
            queryset = queryset.filter(Q(id__icontains=search) | Q(user_id__icontains=search))
        if currency and currency != 'ALL':
            queryset = queryset.filter(currency=currency)
        return queryset.order_by('-created_at')


class AccountDetailView(generics.RetrieveUpdateAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    lookup_field = 'id'

    def perform_update(self, serializer):
        from django.utils import timezone
        previous = Account.objects.only('is_frozen').get(pk=serializer.instance.pk)
        account = serializer.save()
        if 'is_frozen' in serializer.validated_data:
            account.frozen_at = timezone.now() if account.is_frozen else None
            account.save(update_fields=['is_frozen', 'frozen_at', 'updated_at'])
            record_audit(
                self.request.user.username,
                'account_freeze' if account.is_frozen else 'account_unfreeze',
                success=True,
                object_type='Account',
                object_id=account.id,
                metadata={'previous_is_frozen': previous.is_frozen, 'is_frozen': account.is_frozen},
                request=self.request,
            )


class LedgerEntryListView(generics.ListAPIView):
    serializer_class = LedgerEntrySerializer

    def get_queryset(self):
        from django.db.models import Q
        queryset = LedgerEntry.objects.select_related('debit_account', 'credit_account').all()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(id__icontains=search)
                | Q(description__icontains=search)
                | Q(debit_account_id__icontains=search)
                | Q(credit_account_id__icontains=search)
                | Q(idempotency_key__icontains=search)
            )
        return queryset.order_by('-created_at')


class LedgerEntryDetailView(generics.RetrieveAPIView):
    queryset = LedgerEntry.objects.select_related('debit_account', 'credit_account').all()
    serializer_class = LedgerEntrySerializer
    lookup_field = 'id'


class IsSuperuser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class StaffAccountListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsSuperuser]
    serializer_class = StaffAccountSerializer
    pagination_class = None

    def get_queryset(self):
        return get_user_model().objects.filter(is_staff=True).order_by("username")


class StaffAccountDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsSuperuser]
    serializer_class = StaffAccountSerializer
    lookup_field = "pk"
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return get_user_model().objects.filter(is_staff=True)


class AccountCreateView(generics.CreateAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountCreateSerializer


class WebhookEventListView(generics.ListAPIView):
    queryset = WebhookOutbox.objects.all().order_by('-created_at')
    serializer_class = WebhookEventSerializer


class AuditLogListView(generics.ListAPIView):
    permission_classes = [IsSuperuser]
    queryset = AuditLog.objects.all().order_by('-created_at')
    serializer_class = AuditLogSerializer


class ReconciliationView(APIView):
    def get(self, request, *args, **kwargs):
        debit_total = LedgerEntry.objects.aggregate(total=Sum('amount'))['total'] or 0
        credit_total = LedgerEntry.objects.aggregate(total=Sum('amount'))['total'] or 0
        currency_totals = list(Account.objects.values('currency').annotate(account_count=Count('id'), balance=Sum('balance')).order_by('currency'))
        frozen_count = Account.objects.filter(is_frozen=True).count()
        discrepancy = debit_total - credit_total
        return Response({
            'entry_count': LedgerEntry.objects.count(),
            'debit_total': debit_total,
            'credit_total': credit_total,
            'discrepancy': discrepancy,
            'balanced': discrepancy == 0,
            'currency_totals': currency_totals,
            'frozen_account_count': frozen_count,
            'generated_at': timezone.now(),
        })


class OperationalAlertsView(APIView):
    def get(self, request, *args, **kwargs):
        low_balance_threshold = int(request.query_params.get('low_balance_threshold', 100))
        large_transfer_threshold = int(request.query_params.get('large_transfer_threshold', 10000))
        low_balance = list(Account.objects.filter(balance__lt=low_balance_threshold).values('id', 'user_id', 'balance', 'currency', 'is_frozen').order_by('balance')[:25])
        large_transfers = list(LedgerEntry.objects.filter(amount__gte=large_transfer_threshold).values('id', 'amount', 'description', 'created_at').order_by('-created_at')[:25])
        failed_webhooks = WebhookOutbox.objects.filter(status='FAILED').count()
        alerts = []
        for account in low_balance:
            alerts.append({'type': 'LOW_BALANCE', 'severity': 'warning', 'message': f"Account {account['id']} has balance {account['balance']} {account['currency']}", 'object_id': str(account['id'])})
        if failed_webhooks:
            alerts.append({'type': 'FAILED_WEBHOOKS', 'severity': 'critical', 'message': f'{failed_webhooks} webhook events are in FAILED status.', 'object_id': ''})
        for transfer in large_transfers:
            alerts.append({'type': 'LARGE_TRANSFER', 'severity': 'info', 'message': f"Large transfer recorded: {transfer['amount']} units", 'object_id': str(transfer['id'])})
        return Response({'count': len(alerts), 'alerts': alerts, 'thresholds': {'low_balance': low_balance_threshold, 'large_transfer': large_transfer_threshold}, 'generated_at': timezone.now()})
