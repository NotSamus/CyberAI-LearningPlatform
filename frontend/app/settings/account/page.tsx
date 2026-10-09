"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import { useMe } from "@/lib/useMe";

// Everyone's own account: who you are logged in as, and changing your password.
export default function MyAccount() {
  const me = useMe();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [changed, setChanged] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setChanged(false);
    if (next !== repeat) {
      setError("The two new passwords are not the same.");
      return;
    }
    setBusy(true);
    try {
      // The server checks the current password again and sets the new one; nothing is kept here.
      await api("/auth/password", {
        method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ current_password: current, new_password: next }),
      });
      setChanged(true);
      setCurrent("");
      setNext("");
      setRepeat("");
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  return (
    <>
      <h1>My account</h1>
      {me && (
        <p className="muted">
          Logged in as <strong>{me.name}</strong> ({me.username}), {me.is_admin ? `${me.role} and admin` : me.role}.
        </p>
      )}

      <h2>Change password</h2>
      <form className="stack" onSubmit={submit}>
        <label>
          Current password
          <input type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
        </label>
        <label>
          New password (at least 8 characters)
          <input type="password" autoComplete="new-password" required minLength={8} maxLength={256} value={next} onChange={(e) => setNext(e.target.value)} />
        </label>
        <label>
          New password again
          <input type="password" autoComplete="new-password" required minLength={8} maxLength={256} value={repeat} onChange={(e) => setRepeat(e.target.value)} />
        </label>
        <div>
          <button type="submit" disabled={busy}>{busy ? "Changing…" : "Change password"}</button>
        </div>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {changed && (
        <p className="notice" role="status">
          Your password is changed. You stay logged in here; every other device that was logged in to this account has been logged out.
        </p>
      )}
    </>
  );
}
