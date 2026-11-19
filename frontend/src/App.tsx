import { FormEvent, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Download,
  FileClock,
  Landmark,
  LoaderCircle,
  LogOut,
  SearchX,
  SlidersHorizontal,
  RefreshCw,
  Search,
  ShieldCheck,
  TrendingUp,
  WalletCards,
  X,
} from "lucide-react";
import { Account, api, LedgerEntry, Page, TOKEN_KEY } from "./api";

type View = "overview" | "accounts" | "entries";

const emptyPage = <T,>(): Page<T> => ({ count: 0, next: null, previous: null, results: [] });

function amount(value: number, currency: string) {
  return `${currency} ${value.toLocaleString("en-US")}`;
}

function timestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function exportCsv(filename: string, rows: Array<Record<string, string | number>>) {
  if (!rows.length) return;
  const columns = Object.keys(rows[0]);
  const quote = (value: string | number) => `"${String(value).replaceAll('"', '""')}"`;
  const content = [columns.map(quote).join(","), ...rows.map((row) => columns.map((column) => quote(row[column])).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatCompact(value: number) {
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function ActivityChart({ entries }: { entries: LedgerEntry[] }) {
  const points = [...entries].reverse().map((entry) => entry.amount);
  const normalized = points.length > 1
    ? points.map((value, index) => ({
        x: 8 + (index / (points.length - 1)) * 284,
        y: 82 - (value / Math.max(...points, 1)) * 62,
      }))
    : points.length === 1 ? [{ x: 150, y: 51 }] : [];
  const line = normalized.map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`).join(" ");
  const area = `${line} L292,92 L8,92 Z`;
  const latest = points.at(-1) ?? 0;
  const average = points.length ? Math.round(points.reduce((sum, value) => sum + value, 0) / points.length) : 0;

  return (
    <section className="overview-panel activity-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">TRANSFER VOLUME</p><h2>Recent activity</h2></div>
        <span className="scope-tag"><FileClock size={13} /> Latest {entries.length} {entries.length === 1 ? "record" : "records"}</span>
      </div>
      <div className="chart-summary"><strong>{formatCompact(latest)} <small>units</small></strong><span>Latest recorded transfer</span></div>
      <div aria-label="Transfer amount trend for the latest ledger entries" className="chart-wrap" role="img">
        <svg className="activity-chart" viewBox="0 0 300 100" preserveAspectRatio="none">
          <defs><linearGradient id="activity-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#2c8a65" stopOpacity=".23" /><stop offset="100%" stopColor="#2c8a65" stopOpacity="0" /></linearGradient></defs>
          <path d="M8 92H292 M8 52H292 M8 12H292" className="chart-grid" />
          {normalized.length > 1 && <path d={area} className="chart-area" />}
          {normalized.length > 1 && <path d={line} className="chart-line" />}
          {normalized.length === 1 && <circle cx={normalized[0].x} cy={normalized[0].y} r="4" className="chart-point" />}
          {normalized.length > 1 && <circle cx={normalized.at(-1)?.x} cy={normalized.at(-1)?.y} r="3.5" className="chart-point" />}
        </svg>
        {!entries.length && <span className="chart-empty">No transfer data on this page</span>}
      </div>
      <div className="chart-foot"><span>Page average <strong>{formatCompact(average)} units</strong></span><span>Most recent first</span></div>
    </section>
  );
}

function AccountDetailDialog({
  account,
  entries,
  onClose,
}: {
  account: Account;
  entries: LedgerEntry[];
  onClose: () => void;
}) {
  const related = entries.filter((entry) => entry.debit_account_id === account.id || entry.credit_account_id === account.id);
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-labelledby="account-detail-title" aria-modal="true" className="account-dialog" role="dialog">
        <div className="dialog-heading">
          <div><p className="eyebrow">ACCOUNT PROFILE</p><h2 id="account-detail-title">Account details</h2></div>
          <button aria-label="Close account details" className="icon-button" onClick={onClose} type="button"><X size={19} /></button>
        </div>
        <div className="account-balance-block"><span>AVAILABLE BALANCE</span><strong>{amount(account.balance, account.currency)}</strong><small>{account.currency} ledger units</small></div>
        <dl className="detail-grid">
          <div><dt>Account ID</dt><dd>{account.id}</dd></div>
          <div><dt>Owner ID</dt><dd>{account.user_id}</dd></div>
          <div><dt>Created</dt><dd>{timestamp(account.created_at)}</dd></div>
          <div><dt>Last updated</dt><dd>{timestamp(account.updated_at)}</dd></div>
        </dl>
        <div className="related-heading"><h3>Recent account activity</h3><span>{related.length} on this page</span></div>
        {related.length ? <div className="related-list">{related.map((entry) => {
          const outgoing = entry.debit_account_id === account.id;
          return <div className="related-row" key={entry.id}>
            <span className={outgoing ? "related-icon outgoing" : "related-icon incoming"}>{outgoing ? <ArrowUpRight size={15} /> : <ArrowDownLeft size={15} />}</span>
            <span className="related-copy"><strong>{outgoing ? "Outgoing transfer" : "Incoming transfer"}</strong><small>{timestamp(entry.created_at)}</small></span>
            <strong className={outgoing ? "related-amount outgoing-text" : "related-amount incoming-text"}>{outgoing ? "−" : "+"}{entry.amount.toLocaleString("en-US")}</strong>
          </div>;
        })}</div> : <div className="related-empty">No matching activity in the current ledger page.</div>}
      </section>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onLogin(username, password);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="brand-mark"><Landmark size={21} strokeWidth={2.2} /></div>
        <p className="eyebrow">NUVEXA / OPERATIONS</p>
        <h1>Staff sign in</h1>
        <p className="login-copy">Authenticate with your ledger operations account.</p>
        <form className="login-form" onSubmit={submit}>
          <label>
            Username
            <input autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            Password
            <input autoComplete="current-password" required type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error && <p className="form-error"><AlertCircle size={16} />{error}</p>}
          <button className="button button-primary login-submit" disabled={busy} type="submit">
            {busy ? <LoaderCircle className="spin" size={17} /> : <ShieldCheck size={17} />}
            {busy ? "Signing in" : "Sign in securely"}
          </button>
        </form>
        <p className="login-footnote">Staff accounts only. Access is recorded by the API.</p>
      </section>
      <aside className="login-aside">
        <div className="aside-orbit orbit-one" />
        <div className="aside-orbit orbit-two" />
        <span className="aside-index">LEDGER SYSTEM / 01</span>
        <div className="aside-message">
          <span className="aside-rule" />
          <p>Every movement,<br />accounted for.</p>
          <span className="aside-subtitle">Transactional operations console</span>
        </div>
        <span className="aside-version">DOUBLE-ENTRY · AUDIT READY</span>
      </aside>
    </main>
  );
}

function TransferDialog({
  accounts,
  onClose,
  onComplete,
}: {
  accounts: Account[];
  onClose: () => void;
  onComplete: (source: string, destination: string, amount: number, idempotencyKey: string) => Promise<void>;
}) {
  const [source, setSource] = useState("");
  const [destination, setDestination] = useState("");
  const [value, setValue] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const amountValue = Number(value);
  const valid = source && destination && source !== destination && Number.isSafeInteger(amountValue) && amountValue > 0;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirming) {
      setConfirming(true);
      return;
    }

    setBusy(true);
    setError("");
    const key = idempotencyKey || crypto.randomUUID();
    setIdempotencyKey(key);
    try {
      await onComplete(source, destination, amountValue, key);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Transfer could not be completed.");
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-labelledby="transfer-title" aria-modal="true" className="transfer-dialog" role="dialog">
        <div className="dialog-heading">
          <div>
            <p className="eyebrow">LEDGER ACTION</p>
            <h2 id="transfer-title">New transfer</h2>
          </div>
          <button aria-label="Close transfer" className="icon-button" onClick={onClose} type="button"><X size={19} /></button>
        </div>
        <form onSubmit={submit}>
          <label>
            From account ID
            <input autoComplete="off" list="account-options" placeholder="UUID" required value={source} onChange={(event) => { setSource(event.target.value); setConfirming(false); setIdempotencyKey(""); }} />
          </label>
          <label>
            To account ID
            <input autoComplete="off" list="account-options" placeholder="UUID" required value={destination} onChange={(event) => { setDestination(event.target.value); setConfirming(false); setIdempotencyKey(""); }} />
          </label>
          <datalist id="account-options">
            {accounts.map((account) => <option key={account.id} value={account.id}>{account.currency} · {amount(account.balance, account.currency)}</option>)}
          </datalist>
          <label>
            Amount <span className="field-note">whole ledger units</span>
            <input inputMode="numeric" min="1" placeholder="0" required step="1" type="number" value={value} onChange={(event) => { setValue(event.target.value); setConfirming(false); setIdempotencyKey(""); }} />
          </label>
          <p className="transfer-notice">Transfers are final and recorded in the ledger. Verify both account IDs before confirming.</p>
          {confirming && valid && (
            <div className="confirm-summary">
              <span>Confirm {amount(amountValue, "units")} transfer</span>
              <small>{source.slice(0, 8)}... to {destination.slice(0, 8)}...</small>
            </div>
          )}
          {error && <p className="form-error"><AlertCircle size={16} />{error}</p>}
          <div className="dialog-actions">
            <button className="button button-quiet" onClick={onClose} type="button">Cancel</button>
            <button className="button button-primary" disabled={!valid || busy} type="submit">
              {busy ? <LoaderCircle className="spin" size={16} /> : <ArrowLeftRight size={16} />}
              {busy ? "Processing" : confirming ? "Confirm transfer" : "Review transfer"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY));
  const [view, setView] = useState<View>("overview");
  const [pageNumber, setPageNumber] = useState(1);
  const [accounts, setAccounts] = useState<Page<Account>>(emptyPage());
  const [entries, setEntries] = useState<Page<LedgerEntry>>(emptyPage());
  const [loading, setLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"checking" | "connected" | "offline">("checking");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");
  const [currencyFilter, setCurrencyFilter] = useState("all");
  const [sortOrder, setSortOrder] = useState("recent");
  const [refreshKey, setRefreshKey] = useState(0);
  const [showTransfer, setShowTransfer] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setLoading(true);
    setConnectionStatus("checking");
    setError("");
    Promise.all([
      api.accounts(pageNumber, controller.signal),
      api.entries(pageNumber, controller.signal),
    ]).then(([accountPage, entryPage]) => {
      setConnectionStatus("connected");
      setAccounts(accountPage);
      setEntries(entryPage);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setConnectionStatus("offline");
        setError(reason instanceof Error ? reason.message : "Unable to load ledger data.");
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [token, pageNumber, refreshKey]);

  async function signIn(username: string, password: string) {
    const result = await api.login(username, password);
    sessionStorage.setItem(TOKEN_KEY, result.token);
    setToken(result.token);
  }

  async function signOut() {
    try {
      await api.logout();
    } finally {
      sessionStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setAccounts(emptyPage());
      setEntries(emptyPage());
    }
  }

  async function completeTransfer(source: string, destination: string, transferAmount: number, idempotencyKey: string) {
    const result = await api.transfer(source, destination, transferAmount, idempotencyKey);
    setShowTransfer(false);
    setSuccess(`Transfer ${result.transaction_id} authorized.`);
    setRefreshKey((current) => current + 1);
  }

  if (!token) return <Login onLogin={signIn} />;

  const accountRows = accounts.results.filter((account) => {
    const query = search.trim().toLowerCase();
    const matchesQuery = !query || account.id.toLowerCase().includes(query) || account.user_id.toLowerCase().includes(query);
    return matchesQuery && (currencyFilter === "all" || account.currency === currencyFilter);
  }).sort((left, right) => sortOrder === "balance"
    ? right.balance - left.balance
    : new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  const entryRows = entries.results.filter((entry) => {
    const query = search.trim().toLowerCase();
    return !query || entry.id.toLowerCase().includes(query) || entry.debit_account_id.toLowerCase().includes(query) || entry.credit_account_id.toLowerCase().includes(query) || entry.description.toLowerCase().includes(query);
  }).sort((left, right) => sortOrder === "amount"
    ? right.amount - left.amount
    : new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  const isAccounts = view === "accounts";
  const isOverview = view === "overview";
  const currentCount = isAccounts ? accounts.count : entries.count;
  const canGoNext = isAccounts ? Boolean(accounts.next) : Boolean(entries.next);
  const canGoPrevious = isAccounts ? Boolean(accounts.previous) : Boolean(entries.previous);
  const currencyTotals = accounts.results.reduce<Record<string, { count: number; balance: number }>>((totals, account) => {
    const currencyTotal = totals[account.currency] ?? { count: 0, balance: 0 };
    currencyTotal.count += 1;
    currencyTotal.balance += account.balance;
    totals[account.currency] = currencyTotal;
    return totals;
  }, {});

  function downloadCurrentView() {
    if (isAccounts) {
      exportCsv("ledger-accounts.csv", accountRows.map((account) => ({
        account_id: account.id,
        user_id: account.user_id,
        balance: account.balance,
        currency: account.currency,
        created_at: account.created_at,
        updated_at: account.updated_at,
      })));
      return;
    }
    exportCsv("ledger-entries.csv", entryRows.map((entry) => ({
      entry_id: entry.id,
      source_account_id: entry.debit_account_id,
      destination_account_id: entry.credit_account_id,
      amount: entry.amount,
      description: entry.description,
      created_at: entry.created_at,
    })));
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a aria-label="Nuvexa operations home" className="brand" href="#home">
          <span className="brand-mark"><Landmark size={20} strokeWidth={2.2} /></span>
          <span className="brand-name">Nuvexa</span>
        </a>
        <div className="sidebar-label">OPERATIONS</div>
        <nav aria-label="Operations views" className="side-nav">
          <button aria-current={isOverview ? "page" : undefined} className={isOverview ? "nav-item active" : "nav-item"} onClick={() => { setView("overview"); setPageNumber(1); setSearch(""); }}>
            <TrendingUp size={18} /> Overview
          </button>
          <button aria-current={isAccounts ? "page" : undefined} className={isAccounts ? "nav-item active" : "nav-item"} onClick={() => { setView("accounts"); setPageNumber(1); setSearch(""); setCurrencyFilter("all"); }}>
            <WalletCards size={18} /> Accounts
          </button>
          <button aria-current={view === "entries" ? "page" : undefined} className={view === "entries" ? "nav-item active" : "nav-item"} onClick={() => { setView("entries"); setPageNumber(1); setSearch(""); }}>
            <ArrowLeftRight size={18} /> Ledger entries
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className={`connection-state connection-${connectionStatus}`}><span className="status-dot" /> API {connectionStatus === "checking" ? "checking" : connectionStatus}</div>
          <div className="environment-label">PRODUCTION WORKSPACE</div>
          <button className="nav-item signout-button" onClick={() => void signOut()}><LogOut size={17} /> Sign out</button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb"><span>Operations</span><span className="breadcrumb-slash">/</span><strong>{isOverview ? "Overview" : isAccounts ? "Accounts" : "Ledger entries"}</strong></div>
          <div className="topbar-actions">
            <span className="secure-label"><ShieldCheck size={15} /> STAFF ACCESS</span>
            <button aria-label="Refresh ledger data" className="icon-button" disabled={loading} onClick={() => setRefreshKey((current) => current + 1)} title="Refresh data"><RefreshCw className={loading ? "spin" : ""} size={17} /></button>
          </div>
        </header>

        <div className="content-wrap">
          <div className="page-heading">
            <div>
              <p className="eyebrow">TRANSACTIONAL LEDGER / OPERATIONS</p>
              <h1>{isOverview ? "Operations overview" : isAccounts ? "Accounts" : "Ledger entries"}</h1>
              <p className="page-subtitle">{isOverview ? "A live view of account coverage and recorded movement." : isAccounts ? "Review account balances and move funds between accounts." : "Audit completed transfers and their account movements."}</p>
            </div>
            <button className="button button-primary new-transfer" onClick={() => { setSuccess(""); setShowTransfer(true); }}><ArrowLeftRight size={17} /> New transfer</button>
          </div>

          {error && <div className="notice notice-error"><AlertCircle size={17} />{error}<button aria-label="Dismiss error" onClick={() => setError("")}><X size={16} /></button></div>}
          {success && <div className="notice notice-success"><CircleCheck size={17} />{success}<button aria-label="Dismiss confirmation" onClick={() => setSuccess("")}><X size={16} /></button></div>}

          <section aria-label="Ledger summary" className="summary-strip">
            <div className="summary-item"><span className="summary-label">TOTAL ACCOUNTS</span><strong>{accounts.count.toLocaleString("en-US")}</strong><span className="summary-detail">All currencies · database count</span></div>
            <div className="summary-item"><span className="summary-label">LEDGER ENTRIES</span><strong>{entries.count.toLocaleString("en-US")}</strong><span className="summary-detail">All recorded transfers</span></div>
            <div className="summary-item summary-status"><span className="summary-label">LATEST PAGE VOLUME</span><strong>{formatCompact(entries.results.reduce((total, entry) => total + entry.amount, 0))} <small>units</small></strong><span className="summary-detail">Sum of latest {entries.results.length} entry amounts</span></div>
          </section>

          {isOverview && (
            <div className="overview-grid">
              <ActivityChart entries={entries.results} />
              <section className="overview-panel currency-panel">
                <div className="panel-heading"><div><p className="eyebrow">ACCOUNT COVERAGE</p><h2>By currency</h2></div><span className="currency-panel-icon"><WalletCards size={17} /></span></div>
                {Object.entries(currencyTotals).length ? <div className="currency-list">{Object.entries(currencyTotals).map(([currency, totals], index) => {
                  const percentage = accounts.results.length ? (totals.count / accounts.results.length) * 100 : 0;
                  return <div className="currency-row" key={currency}>
                    <span className={`currency-badge currency-badge-${index % 4}`}>{currency}</span>
                    <span className="currency-row-main"><span className="currency-row-title"><strong>{currency}</strong><small>{totals.count} on this page</small></span><span className="currency-track"><span style={{ width: `${percentage}%` }} /></span></span>
                    <strong className="currency-total">{formatCompact(totals.balance)}</strong>
                  </div>;
                })}</div> : <div className="currency-empty">Currency totals appear when account data is available.</div>}
                <p className="panel-footnote">Balances summarize the current account page only.</p>
              </section>
            </div>
          )}

          <section className="data-section">
            <div className="section-toolbar">
              <div>
                <h2>{isAccounts ? "Account register" : isOverview ? "Latest ledger activity" : "Ledger entries"}</h2>
                <p>{currentCount.toLocaleString("en-US")} records · page {pageNumber}</p>
              </div>
              <div className="table-tools">
                <label className="search-field">
                  <Search size={16} />
                  <input aria-label={isAccounts ? "Search accounts" : "Search ledger entries"} placeholder={isAccounts ? "Search accounts" : "Search entries"} value={search} onChange={(event) => setSearch(event.target.value)} />
                </label>
                {isAccounts ? <label className="select-field"><SlidersHorizontal size={14} /><select aria-label="Filter by currency" value={currencyFilter} onChange={(event) => setCurrencyFilter(event.target.value)}><option value="all">All currencies</option>{Object.keys(currencyTotals).sort().map((currency) => <option key={currency} value={currency}>{currency}</option>)}</select></label> : <label className="select-field"><SlidersHorizontal size={14} /><select aria-label="Sort ledger entries" value={sortOrder} onChange={(event) => setSortOrder(event.target.value)}><option value="recent">Most recent</option><option value="amount">Largest amount</option></select></label>}
                <button className="button button-quiet export-button" disabled={loading || (isAccounts ? accountRows.length === 0 : entryRows.length === 0)} onClick={downloadCurrentView} title="Export visible records as CSV"><Download size={15} /> Export CSV</button>
              </div>
            </div>

            {loading ? (
              <div className="loading-state"><LoaderCircle className="spin" size={22} />Loading ledger data</div>
            ) : isAccounts ? (
              accountRows.length ? (
                <div className="table-scroll">
                  <table>
                    <thead><tr><th>ACCOUNT</th><th>USER ID</th><th>BALANCE</th><th>CURRENCY</th><th>CREATED</th></tr></thead>
                    <tbody>{accountRows.map((account) => (
                      <tr key={account.id}>
                        <td><button className="table-link account-id" onClick={() => setSelectedAccount(account)}>{account.id}</button></td>
                        <td className="mono muted-cell">{account.user_id}</td>
                        <td className="amount-cell">{amount(account.balance, account.currency)}</td>
                        <td><span className="currency-tag">{account.currency}</span></td>
                        <td className="date-cell">{timestamp(account.created_at)}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              ) : <div className="empty-state"><SearchX size={20} /><strong>No matching accounts</strong><span>Adjust your search or currency filter.</span></div>
            ) : entryRows.length ? (
              <div className="table-scroll">
                <table>
                  <thead><tr><th>ENTRY</th><th>FROM ACCOUNT</th><th>TO ACCOUNT</th><th>AMOUNT</th><th>RECORDED</th></tr></thead>
                  <tbody>{entryRows.map((entry) => (
                    <tr key={entry.id}>
                      <td><span className="entry-id">{entry.id}</span><span className="entry-description">{entry.description || "Ledger transfer"}</span></td>
                      <td className="mono muted-cell"><ArrowUpRight className="flow-icon outgoing" size={14} />{entry.debit_account_id}</td>
                      <td className="mono muted-cell"><ArrowDownLeft className="flow-icon incoming" size={14} />{entry.credit_account_id}</td>
                      <td className="amount-cell">{entry.amount.toLocaleString("en-US")} <span className="units-label">units</span></td>
                      <td className="date-cell">{timestamp(entry.created_at)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            ) : <div className="empty-state"><SearchX size={20} /><strong>{search ? "No matching ledger entries" : "No ledger entries yet"}</strong><span>{search ? "Try a different entry, account ID, or description." : "Completed transfers will appear here."}</span></div>}

            <footer className="table-footer">
              <span>Showing {currentCount ? Math.min((pageNumber - 1) * 25 + 1, currentCount) : 0}–{Math.min(pageNumber * 25, currentCount)} of {currentCount.toLocaleString("en-US")}</span>
              <div className="pagination-controls">
                <button aria-label="Previous page" className="icon-button" disabled={!canGoPrevious || loading} onClick={() => setPageNumber((current) => Math.max(1, current - 1))}><ChevronLeft size={17} /></button>
                <span>{pageNumber}</span>
                <button aria-label="Next page" className="icon-button" disabled={!canGoNext || loading} onClick={() => setPageNumber((current) => current + 1)}><ChevronRight size={17} /></button>
              </div>
            </footer>
          </section>
          <p className="data-note">Balances and activity are served directly from the ledger database. Amounts are shown in stored ledger units.</p>
        </div>
      </main>
      {showTransfer && <TransferDialog accounts={accounts.results} onClose={() => setShowTransfer(false)} onComplete={completeTransfer} />}
      {selectedAccount && <AccountDetailDialog account={selectedAccount} entries={entries.results} onClose={() => setSelectedAccount(null)} />}
    </div>
  );
}

export default App;