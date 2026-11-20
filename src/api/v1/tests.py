import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from src.domains.ledger.models.journal import Account, LedgerEntry
from src.domains.ledger.services.transfer import LedgerTransferService


def dump_response(response, label=None):
    try:
        body = response.json()
    except Exception:
        body = response.content.decode('utf-8', errors='replace')
    label_msg = f" [{label}]" if label else ""
    print(f"\nRESPONSE{label_msg}: status={response.status_code} body={body}\n")


def authenticate_staff_client(client):
    user = get_user_model().objects.create_user(
        username=f"staff-{uuid.uuid4()}",
        password="test-password",
        is_staff=True,
    )
    token = Token.objects.create(user=user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Token {token.key}"


class LedgerTransferAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        authenticate_staff_client(self.client)
        self.source_account = Account.objects.create(
            user_id=uuid.uuid4(),
            balance=1000,
            currency="USD",
        )
        self.destination_account = Account.objects.create(
            user_id=uuid.uuid4(),
            balance=500,
            currency="USD",
        )

    def test_transfer_endpoint_requires_idempotency_key(self):
        response = self.client.post(
            "/api/v1/transfers",
            {
                "source_account_id": str(self.source_account.id),
                "destination_account_id": str(self.destination_account.id),
                "amount": 100,
            },
            content_type="application/json",
        )

        dump_response(response, "missing-idempotency")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_transfer_endpoint_creates_transaction(self):
        response = self.client.post(
            "/api/v1/transfers",
            {
                "source_account_id": str(self.source_account.id),
                "destination_account_id": str(self.destination_account.id),
                "amount": 100,
            },
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="api-test-key",
        )

        dump_response(response, "transfer-success")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "AUTHORIZED")

        self.source_account.refresh_from_db()
        self.destination_account.refresh_from_db()

        self.assertEqual(self.source_account.balance, 900)
        self.assertEqual(self.destination_account.balance, 600)

    def test_transfer_endpoint_rejects_invalid_amount(self):
        response = self.client.post(
            "/api/v1/transfers",
            {
                "source_account_id": str(self.source_account.id),
                "destination_account_id": str(self.destination_account.id),
                "amount": -50,
            },
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="api-test-key-2",
        )

        dump_response(response, "invalid-amount")
        self.assertEqual(response.status_code, 400)
        self.assertIn("amount", response.json())

    def test_transfer_endpoint_rejects_non_integer_amount(self):
        response = self.client.post(
            "/api/v1/transfers",
            {
                "source_account_id": str(self.source_account.id),
                "destination_account_id": str(self.destination_account.id),
                "amount": "not-an-integer",
            },
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="invalid-amount-key",
        )
        self.assertEqual(response.status_code, 400)

    def test_transfer_endpoint_rejects_same_account(self):
        response = self.client.post(
            "/api/v1/transfers",
            {
                "source_account_id": str(self.source_account.id),
                "destination_account_id": str(self.source_account.id),
                "amount": 100,
            },
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="same-account-key",
        )
        self.assertEqual(response.status_code, 400)

    def test_cached_transfer_response_is_not_available_without_staff_auth(self):
        payload = {
            "source_account_id": str(self.source_account.id),
            "destination_account_id": str(self.destination_account.id),
            "amount": 100,
        }
        staff_response = self.client.post(
            "/api/v1/transfers",
            payload,
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="scoped-idempotency-key",
        )
        anonymous_response = Client().post(
            "/api/v1/transfers",
            payload,
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="scoped-idempotency-key",
        )
        self.assertEqual(staff_response.status_code, 201)
        self.assertEqual(anonymous_response.status_code, 401)


class AccountEndpointsTests(TestCase):
    def setUp(self):
        self.client = Client()
        authenticate_staff_client(self.client)
        self.account = Account.objects.create(
            user_id=uuid.uuid4(),
            balance=1200,
            currency="USD",
        )

    def test_account_list_returns_accounts(self):
        response = self.client.get("/api/v1/accounts/")
        dump_response(response, "account-list")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json()["results"], list)
        self.assertGreaterEqual(len(response.json()["results"]), 1)

    def test_account_detail_returns_account(self):
        response = self.client.get(f"/api/v1/accounts/{self.account.id}/")
        dump_response(response, "account-detail")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(self.account.id))

    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/api/v1/health/")
        dump_response(response, "health-check")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_account_list_requires_staff_authentication(self):
        response = Client().get("/api/v1/accounts/")
        self.assertEqual(response.status_code, 401)

    def test_non_staff_user_cannot_obtain_token(self):
        user = get_user_model().objects.create_user(username="customer", password="customer-password")
        response = Client().post(
            "/api/v1/auth/token/",
            {"username": user.username, "password": "customer-password"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)


class StaffAccountManagementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(username="root-admin", password="root-password-123")
        self.superuser_token = Token.objects.create(user=self.superuser)

    def request(self, method, path, data=None):
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = f"Token {self.superuser_token.key}"
        return getattr(client, method)(path, data or {}, content_type="application/json")

    def test_superuser_can_create_and_reset_staff_account(self):
        created = self.request("post", "/api/v1/staff/accounts/", {
            "username": "operations-user",
            "password": "operations-password-123",
        })
        self.assertEqual(created.status_code, 201)

        User = get_user_model()
        staff = User.objects.get(username="operations-user")
        self.assertTrue(staff.is_staff)

        reset = self.request("patch", f"/api/v1/staff/accounts/{staff.pk}/", {
            "password": "new-operations-password-123",
        })
        self.assertEqual(reset.status_code, 200)
        staff.refresh_from_db()
        self.assertTrue(staff.check_password("new-operations-password-123"))

    def test_regular_staff_cannot_manage_staff_accounts(self):
        User = get_user_model()
        staff = User.objects.create_user(username="regular", password="regular-password-123", is_staff=True)
        token = Token.objects.create(user=staff)
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = f"Token {token.key}"
        response = client.post("/api/v1/staff/accounts/", {
            "username": "unauthorized",
            "password": "unauthorized-password-123",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 403)


class LedgerEntryEndpointsTests(TestCase):
    def setUp(self):
        self.client = Client()
        authenticate_staff_client(self.client)
        self.source_account = Account.objects.create(
            user_id=uuid.uuid4(),
            balance=1000,
            currency="USD",
        )
        self.destination_account = Account.objects.create(
            user_id=uuid.uuid4(),
            balance=500,
            currency="USD",
        )
        self.entry = LedgerEntry.objects.create(
            idempotency_key="entry-test-key",
            debit_account=self.source_account,
            credit_account=self.destination_account,
            amount=100,
            description="Test ledger entry",
        )

    def test_ledger_entry_list_returns_entries(self):
        response = self.client.get("/api/v1/ledger-entries/")
        dump_response(response, "ledger-entry-list")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json()["results"], list)
        self.assertGreaterEqual(len(response.json()["results"]), 1)

    def test_ledger_entry_detail_returns_entry(self):
        response = self.client.get(f"/api/v1/ledger-entries/{self.entry.id}/")
        dump_response(response, "ledger-entry-detail")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(self.entry.id))
