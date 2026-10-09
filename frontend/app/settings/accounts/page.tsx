"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type Account, type NewAccount } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import { useMe } from "@/lib/useMe";

const ADMIN_ONLY_ON_SERVER = "Admin accounts are only changed on the server, with the command line tool.";

export default function AccountsSettings() {
  // The server decides who is an admin: /api/admin/users answers 403 for everyone else, and this
  // section only shows anything once that request has succeeded.
  const me = useMe();
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [reset, setReset] = useState<NewAccount | null>(null);     // kept only in this page's memory

  const load = useCallback(() => {
    api<Account[]>("/admin/users").then(setAccounts).catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  async function act<T>(action: () => Promise<T>): Promise<T | null> {
    setError("");
    setReset(null);
    try {
      const result = await action();
      load();
      return result;
    } catch (e) {
      setError(message(e));
      return null;
    }
  }

  async function resetPassword(a: Account) {
    const sure = window.confirm(`Give ${a.name} (${a.username}) a new password? They are logged out everywhere, and their current password stops working.`);
    if (!sure) return;
    const account = await act(() => api<NewAccount>(`/admin/users/${a.id}/reset-password`, { method: "POST" }));
    if (account) setReset(account);
  }

  function remove(a: Account) {
    const sure = window.confirm(
      `Remove the account ${a.name} (${a.username})? Its submissions and grades are deleted and its notebook servers are stopped. ` +
      "The files in its notebook home stay on the server. This cannot be undone.",
    );
    if (sure) act(() => api(`/admin/users/${a.id}`, { method: "DELETE" }));
  }

  if (loadError) return <><h1>Accounts</h1><p className="error" role="alert">{loadError}</p></>;
  if (!accounts) return <><h1>Accounts</h1><p className="muted">Loading…</p></>;

  return (
    <>
      <h1>Accounts</h1>

      <h2>Add an account</h2>
      <AddAccount onCreated={load} />

      <h2>All accounts ({accounts.length})</h2>
      {error && <p className="error" role="alert">{error}</p>}
      {reset && (
        <p className="notice" role="status">
          The new password of <strong>{reset.username}</strong> is <code>{reset.password}</code>
          <br />Give it to them now: it is not stored and will not be shown again. They can change it under Settings &gt; My account.
        </p>
      )}
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Username</th><th>Name</th><th>Role</th><th>GPU</th><th>Notebook user</th><th>Created</th><th></th></tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              editing === a.id
                ? (
                  <EditRow
                    key={a.id}
                    account={a}
                    onCancel={() => setEditing(null)}
                    onSave={async (changes) => {
                      const saved = await act(() => api(`/admin/users/${a.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(changes) }));
                      if (saved) setEditing(null);
                    }}
                  />
                )
                : (
                  <tr key={a.id}>
                    <td>{a.username}</td>
                    <td>{a.name}</td>
                    <td>{a.role}{a.is_admin && ", admin"}</td>
                    <td>{a.gpu_enabled || a.role === "teacher" ? "Yes" : "No"}</td>
                    <td><code>{a.hub_username}</code></td>
                    <td>{new Date(a.created_at).toLocaleDateString()}</td>
                    <td className="actions">
                      <button className="secondary" onClick={() => setEditing(a.id)}>Edit</button>
                      <button className="secondary" disabled={a.is_admin} title={a.is_admin ? ADMIN_ONLY_ON_SERVER : undefined} onClick={() => resetPassword(a)}>
                        New password
                      </button>
                      <button
                        className="secondary danger"
                        disabled={a.is_admin || a.id === me?.id}
                        title={a.is_admin ? ADMIN_ONLY_ON_SERVER : undefined}
                        onClick={() => remove(a)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                )
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        “Notebook user” is the name that account has in the JupyterHub section. A username and a role
        cannot be changed afterwards. Admin rights are given and taken away on the server only.
      </p>
    </>
  );
}

function EditRow({ account, onSave, onCancel }: {
  account: Account;
  onSave: (changes: { name: string; gpu_enabled: boolean }) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(account.name);
  const [gpu, setGpu] = useState(account.gpu_enabled);
  const teacher = account.role === "teacher";       // teachers always have GPU notebooks
  return (
    <tr>
      <td>{account.username}</td>
      <td><input aria-label="Name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} /></td>
      <td>{account.role}{account.is_admin && ", admin"}</td>
      <td>
        <input type="checkbox" aria-label="GPU notebooks" checked={gpu || teacher} disabled={teacher} onChange={(e) => setGpu(e.target.checked)} />
      </td>
      <td><code>{account.hub_username}</code></td>
      <td>{new Date(account.created_at).toLocaleDateString()}</td>
      <td className="actions">
        <button onClick={() => onSave({ name, gpu_enabled: gpu })} disabled={!name.trim()}>Save</button>
        <button className="secondary" onClick={onCancel}>Cancel</button>
      </td>
    </tr>
  );
}

function AddAccount({ onCreated }: { onCreated: () => void }) {
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("student");
  const [gpu, setGpu] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<NewAccount | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setCreated(null);
    try {
      const account = await api<NewAccount>("/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, name, role, gpu_enabled: gpu }),
      });
      setCreated(account);            // kept only in this page's memory, gone on reload
      setUsername("");
      setName("");
      setGpu(false);
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setBusy(false);
  }

  return (
    <>
      <form className="add-account" onSubmit={submit}>
        <label>
          Username
          <input name="new-username" autoComplete="off" autoCapitalize="none" required
            value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          Full name
          <input name="new-name" autoComplete="off" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="student">Student</option>
            <option value="teacher">Teacher</option>
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={gpu || role === "teacher"} disabled={role === "teacher"}
            onChange={(e) => setGpu(e.target.checked)} />
          GPU notebooks
        </label>
        <button type="submit" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {created && (
        <p className="notice" role="status">
          Account <strong>{created.username}</strong> created. Its password is <code>{created.password}</code>
          <br />Give it to them now: it is not stored and will not be shown again.
        </p>
      )}
    </>
  );
}
