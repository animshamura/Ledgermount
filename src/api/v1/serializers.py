from django.contrib.auth import get_user_model
from rest_framework import serializers
from src.domains.ledger.models.journal import Account, LedgerEntry
from src.domains.webhooks.models.outbox import WebhookOutbox


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            'id',
            'user_id',
            'balance',
            'currency',
            'created_at',
            'updated_at',
        ]


class LedgerEntrySerializer(serializers.ModelSerializer):
    debit_account_id = serializers.UUIDField(source='debit_account.id', read_only=True)
    credit_account_id = serializers.UUIDField(source='credit_account.id', read_only=True)

    class Meta:
        model = LedgerEntry
        fields = [
            'id',
            'idempotency_key',
            'debit_account_id',
            'credit_account_id',
            'amount',
            'description',
            'created_at',
        ]


class TransferRequestSerializer(serializers.Serializer):
    source_account_id = serializers.UUIDField()
    destination_account_id = serializers.UUIDField()
    amount = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        if attrs['source_account_id'] == attrs['destination_account_id']:
            raise serializers.ValidationError("Source and destination accounts must differ.")
        return attrs


class StaffAccountSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, required=False, min_length=12)
    is_active = serializers.BooleanField(required=False)

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Username is required.")
        return value

    def create(self, validated_data):
        User = get_user_model()
        username = validated_data["username"]
        password = validated_data.get("password")
        if not password:
            raise serializers.ValidationError({"password": "Password is required when creating an account."})
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError({"username": "A user with this username already exists."})
        return User.objects.create_user(
            username=username,
            password=password,
            is_staff=True,
            is_active=validated_data.get("is_active", True),
        )

    def update(self, instance, validated_data):
        password = validated_data.get("password")
        if password:
            instance.set_password(password)
        if "is_active" in validated_data:
            instance.is_active = validated_data["is_active"]
        instance.save()
        return instance


class AccountCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'user_id', 'balance', 'currency', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_balance(self, value):
        if value < 0:
            raise serializers.ValidationError("Balance must be zero or greater.")
        return value

    def validate_currency(self, value):
        return value.strip().upper()


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookOutbox
        fields = [
            'id',
            'event_type',
            'payload',
            'status',
            'retry_count',
            'last_attempt',
            'created_at',
        ]
