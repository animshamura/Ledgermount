export type Account = {
  id: string;
  user_id: string;
  balance: number;
  currency: string;
  created_at: string;
  updated_at: string;
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

export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
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
  async login(username: string, password: string) {
    return request<{ token: string }>("/api/v1/auth/token/", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },
  logout() {
    return request<void>("/api/v1/auth/logout/", { method: "POST" });
  },
  accounts(page: number, signal?: AbortSignal) {
    return request<Page<Account>>(`/api/v1/accounts/?page=${page}`, { signal });
  },
  entries(page: number, signal?: AbortSignal) {
    return request<Page<LedgerEntry>>(`/api/v1/ledger-entries/?page=${page}`, { signal });
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
};

export { TOKEN_KEY };