from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from src.domains.ledger.services.transfer import LedgerTransferService
from src.domains.ledger.models.journal import Account, LedgerEntry
from .serializers import AccountSerializer, LedgerEntrySerializer, TransferRequestSerializer


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
            return Response({"error": "Invalid staff credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key}, status=status.HTTP_200_OK)


class StaffLogoutView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountListView(generics.ListAPIView):
    queryset = Account.objects.all().order_by('created_at')
    serializer_class = AccountSerializer


class AccountDetailView(generics.RetrieveAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    lookup_field = 'id'


class LedgerEntryListView(generics.ListAPIView):
    queryset = LedgerEntry.objects.select_related('debit_account', 'credit_account').all().order_by('-created_at')
    serializer_class = LedgerEntrySerializer


class LedgerEntryDetailView(generics.RetrieveAPIView):
    queryset = LedgerEntry.objects.select_related('debit_account', 'credit_account').all()
    serializer_class = LedgerEntrySerializer
    lookup_field = 'id'
