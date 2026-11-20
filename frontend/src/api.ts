export type Account = {
  id: string;
  user_id: string;
  balance: number;
  currency: string;
  is_frozen: boolean;
  frozen_at: string | null;
  created_at: string;
  updated_at: string;
};

export type StaffAccount = {
  id: number;
  username: string;
  is_active: boolean;
};

export type LedgerEntry = {
  id: string;
  idempotency_key: string;
  debit_account_id: string;
  credit_account_id: string;
  amount: number;
  description: string;
  created_at: string;
};

export type WebhookEvent = {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: string;
  retry_count: number;
  last_attempt: string | null;
  created_at: string;
};

export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type AuditLog = {
  id: string;
  actor_username: string;
  action: string;
  object_type: string;
  object_id: string;
  success: boolean;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const TOKEN_KEY = "industrial-ledger-token";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) headers.set("Authorization", `Token ${token}`);

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as Record<string, unknown> | null;
    const detail = body?.detail ?? body?.error;
    const fieldErrors = body
      ? Object.entries(body).flatMap(([field, value]) => {
          const messages = Array.isArray(value) ? value : [value];
          return messages.map((message) => typeof message === "string" ? `${field}: ${message}` : "");
        }).filter(Boolean)
      : [];
    const message = typeof detail === "string"
      ? detail
      : fieldErrors.length
        ? fieldErrors.join(" ")
        : `Request failed (${response.status})`;
    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  health() {
    return request<{ status: string }>("/api/v1/health/");
  },
  async login(username: string, password: string) {
    return request<{ token: string; is_superuser: boolean }>('/api/v1/auth/token/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },
  logout() {
    return request<void>("/api/v1/auth/logout/", { method: "POST" });
  },
  accounts(page: number, signal?: AbortSignal, search: string = "", currency: string = "all") {
    const params = new URLSearchParams({ page: String(page) });
    if (search.trim()) params.set("search", search.trim());
    if (currency !== "all") params.set("currency", currency);
    return request<Page<Account>>(`/api/v1/accounts/?${params}`, { signal });
  },
  entries(page: number, signal?: AbortSignal, search: string = "") {
    const params = new URLSearchParams({ page: String(page) });
    if (search.trim()) params.set("search", search.trim());
    return request<Page<LedgerEntry>>(`/api/v1/ledger-entries/?${params}`, { signal });
  },
  transfer(source: string, destination: string, amount: number, idempotencyKey: string) {
    return request<{ transaction_id: string; status: string }>("/api/v1/transfers", {
      method: "POST",
      headers: { "X-Idempotency-Key": idempotencyKey },
      body: JSON.stringify({
        source_account_id: source,
        destination_account_id: destination,
        amount,
      }),
    });
  },
  staffAccounts() {
    return request<StaffAccount[]>('/api/v1/staff/accounts/');
  },
  createStaffAccount(username: string, password: string) {
    return request<StaffAccount>('/api/v1/staff/accounts/', {
      method: 'POST',
      body: JSON.stringify({ username, password, is_active: true }),
    });
  },
  updateStaffAccount(id: number, fields: { password?: string; is_active?: boolean }) {
    return request<StaffAccount>(`/api/v1/staff/accounts/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(fields),
    });
  },
  auditLogs(page: number = 1) {
    return request<Page<AuditLog>>(`/api/v1/audit/?page=${page}`);
  },
  webhookEvents(page: number = 1) {
    return request<Page<WebhookEvent>>(`/api/v1/webhooks/?page=${page}`);
  },
  createAccount(userId: string, balance: number, currency: string) {
    return request<Account>('/api/v1/accounts/create/', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, balance, currency }),
    });
  },
  updateAccountFreeze(accountId: string, isFrozen: boolean) {
    return request<Account>(`/api/v1/accounts/${accountId}/`, {
      method: 'PATCH',
      body: JSON.stringify({ is_frozen: isFrozen }),
    });
  },
  reconciliation() {
    return request<Record<string, unknown>>('/api/v1/reconciliation/');
  },
  operationalAlerts(lowBalanceThreshold: number = 100, largeTransferThreshold: number = 10000) {
    return request<Record<string, unknown>>(`/api/v1/alerts/?low_balance_threshold=${lowBalanceThreshold}&large_transfer_threshold=${largeTransferThreshold}`);
  },
};

export { TOKEN_KEY };