"use client";
import { Cpu, GraduationCap, KeyRound, School, Shield, Trash2, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Chip from "@/components/Chip";
import Dialog from "@/components/Dialog";
import Menu from "@/components/Menu";
import PageHeader from "@/components/PageHeader";
import { api, type Account, type NewAccount } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import { useMe } from "@/lib/useMe";

// A password the server has just made, shown once: when an account is added, or given a new password.
type Shown = { username: string; password: string; created: boolean };

export default function AccountsPage() {
  // The server decides who is an admin: /api/admin/users answers 403 for everyone else, and this
  // page only shows anything once that request has succeeded.
  const me = useMe();
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [shown, setShown] = useState<Shown | null>(null);      // kept only in this page's memory, never in the address

  const load = useCallback(() => {
    api<Account[]>("/admin/users").then(setAccounts).catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  async function resetPassword(a: Account) {
    const sure = window.confirm(`Give ${a.name} (${a.username}) a new password? They are logged out everywhere, and their current password stops working.`);
    if (!sure) return;
    setError("");
    try {
      const account = await api<NewAccount>(`/admin/users/${a.id}/reset-password`, { method: "POST" });
      setShown({ username: account.username, password: account.password, created: false });
      load();
    } catch (e) {
      setError(message(e));
    }
  }

  async function remove(a: Account) {
    const sure = window.confirm(
      `Remove the account ${a.name} (${a.username})? Its submissions and grades are deleted and its notebook servers are stopped. ` +
      "The files in its notebook home stay on the server. This cannot be undone.",
    );
    if (!sure) return;
    setError("");
    try {
      await api(`/admin/users/${a.id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(message(e));
    }
  }

  const header = (
    <PageHeader
      title="Accounts"
      description="Everyone who can log in. A username and a role cannot be changed afterwards."
      actions={accounts && <button onClick={() => setAdding(true)}><UserPlus aria-hidden />Add account</button>}
    />
  );

  if (loadError) return <>{header}<p className="error" role="alert">{loadError}</p></>;
  if (!accounts) return <>{header}<p className="muted">Loading…</p></>;

  return (
    <>
      {header}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="table-box">
        <table>
          <thead>
            <tr><th>Account</th><th>Role</th><th>GPU</th><th>Notebook user</th><th>Created</th><th><span className="visually-hidden">Actions</span></th></tr>
          </thead>
          <tbody>
            {accounts.map((a) => {
              const gpu = a.gpu_enabled || a.role === "teacher";        // teachers always have GPU notebooks
              return (
                <tr key={a.id}>
                  <td className="wrap">
                    <span className="person"><strong>{a.name}</strong><span className="muted">{a.username}</span></span>
                  </td>
                  <td>
                    <span className="badges">
                      <Chip icon={a.role === "teacher" ? School : GraduationCap}>{a.role === "teacher" ? "Teacher" : a.role === "student" ? "Student" : a.role}</Chip>
                      {a.is_admin && <Chip icon={Shield}>Admin</Chip>}
                    </span>
                  </td>
                  <td>
                    {/* Said in words to screen readers, and as a tooltip: the icon and the dash alone say nothing */}
                    {gpu
                      ? <span className="fact gpu" role="img" aria-label="GPU notebooks" title="GPU notebooks"><Cpu aria-hidden /></span>
                      : <span className="muted" title="No GPU notebooks"><span aria-hidden>—</span><span className="visually-hidden">No GPU</span></span>}
                  </td>
                  <td className="wrap"><code>{a.hub_username}</code></td>
                  <td>{new Date(a.created_at).toLocaleDateString()}</td>
                  <td className="end">
                    <span className="cell-actions">
                      <button className="secondary" onClick={() => setEditing(a)}>Edit</button>
                      <Menu
                        label={`More for ${a.username}`}
                        items={[
                          { label: "New password", icon: KeyRound, disabled: a.is_admin, onSelect: () => resetPassword(a) },
                          { label: "Remove", icon: Trash2, danger: true, disabled: a.is_admin || a.id === me?.id, onSelect: () => remove(a) },
                        ]}
                      />
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted hint">
        “Notebook user” is the name that account has in the JupyterHub section. Admin accounts are only changed on
        the server, with the command line tool: admin rights are given and taken away there, so their new password
        and removal are not offered here. You cannot remove your own account.
      </p>

      <AddAccountDialog
        open={adding} onClose={() => setAdding(false)}
        onCreated={(account) => { setAdding(false); setShown({ username: account.username, password: account.password, created: true }); load(); }}
      />
      {editing && (
        <EditAccountDialog
          account={editing} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
      <PasswordDialog shown={shown} onDone={() => setShown(null)} />
    </>
  );
}

// The one time a password is shown. It stays open until the admin says it is noted: Escape and a
// click beside it do not close it.
function PasswordDialog({ shown, onDone }: { shown: Shown | null; onDone: () => void }) {
  return (
    <Dialog open={shown !== null} title={shown?.created ? "Account created" : "New password"} onClose={onDone} dismissible={false}>
      <form onSubmit={(e) => { e.preventDefault(); onDone(); }}>
        <div className="dialog-body">
          <p>The password of <strong>{shown?.username}</strong> is</p>
          <p className="password"><code>{shown?.password}</code></p>
          <p className="muted">
            Give it to them now: it is not stored and will not be shown again. They can change it under My account,
            in the menu under their name.
          </p>
        </div>
        <div className="dialog-foot">
          <button type="submit" autoFocus>I have noted it</button>
        </div>
      </form>
    </Dialog>
  );
}

function AddAccountDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (account: NewAccount) => void }) {
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("student");
  const [gpu, setGpu] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const account = await api<NewAccount>("/admin/users", {
        method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ username, name, role, gpu_enabled: gpu }),
      });
      setUsername("");
      setName("");
      setGpu(false);
      onCreated(account);
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  return (
    <Dialog open={open} title="Add account" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="dialog-body">
          <label>
            Username
            <input name="new-username" autoComplete="off" autoCapitalize="none" autoFocus required
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
            GPU notebooks{role === "teacher" && <span className="muted"> (teachers always have them)</span>}
          </label>
          <p className="muted">The server makes a password for the account and shows it to you once.</p>
          {error && <p className="error" role="alert">{error}</p>}
        </div>
        <div className="dialog-foot">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        </div>
      </form>
    </Dialog>
  );
}

function EditAccountDialog({ account, onClose, onSaved }: { account: Account; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(account.name);
  const [gpu, setGpu] = useState(account.gpu_enabled);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const teacher = account.role === "teacher";       // teachers always have GPU notebooks

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/admin/users/${account.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify({ name, gpu_enabled: gpu }) });
      onSaved();
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }

  return (
    <Dialog open title={`Edit ${account.username}`} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="dialog-body">
          <label>
            Name
            <input required autoFocus maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="check">
            <input type="checkbox" checked={gpu || teacher} disabled={teacher} onChange={(e) => setGpu(e.target.checked)} />
            GPU notebooks{teacher && <span className="muted"> (teachers always have them)</span>}
          </label>
          <p className="muted">The username ({account.username}) and the role cannot be changed.</p>
          {error && <p className="error" role="alert">{error}</p>}
        </div>
        <div className="dialog-foot">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={busy || !name.trim()}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </Dialog>
  );
}
