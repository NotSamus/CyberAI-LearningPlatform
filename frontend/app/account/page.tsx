"use client";
import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import { THEMES, applyTheme, isTheme, shownTheme, type ThemeId } from "@/lib/themes";
import { useMe } from "@/lib/useMe";

// Everyone's own account: who you are logged in as, how the site looks, and changing your password.
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
    <main className="area-page account">
      <PageHeader
        title="My account"
        description={me && <>Logged in as <strong>{me.name}</strong> ({me.username}), {me.is_admin ? `${me.role} and admin` : me.role}.</>}
      />
      {error && <p className="error" role="alert">{error}</p>}
      {changed && (
        <p className="notice" role="status">
          Your password is changed. You stay logged in here; every other device that was logged in to this account has been logged out.
        </p>
      )}

      <Appearance saved={me && isTheme(me.theme) ? me.theme : null} />

      <section className="card">
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
      </section>
    </main>
  );
}

// The theme of this account. It changes the page at once and is then saved on the server; if
// saving fails, the page goes back to the theme it had.
function Appearance({ saved }: { saved: ThemeId | null }) {
  const [chosen, setChosen] = useState<ThemeId | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (saved) setChosen(saved); }, [saved]);

  async function choose(theme: ThemeId) {
    const before = shownTheme();
    setError("");
    setChosen(theme);
    applyTheme(theme);
    setBusy(true);
    try {
      await api("/auth/theme", { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ theme }) });
    } catch (e) {
      setChosen(before);
      applyTheme(before);
      setError(message(e));
    }
    setBusy(false);
  }

  return (
    <section className="card">
      <h2>Appearance</h2>
      <p className="muted">How the site looks for you, on every device you log in on.</p>
      <div className="theme-choices" role="radiogroup" aria-label="Theme">
        {THEMES.map((theme) => (
          <label key={theme.id} className={`theme-choice ${chosen === theme.id ? "chosen" : ""}`}>
            <input
              type="radio" name="theme" value={theme.id} checked={chosen === theme.id}
              disabled={busy || chosen === null} onChange={() => choose(theme.id)}
            />
            {/* A small picture of the theme, in its own colours whichever theme is shown now */}
            <span className={`theme-preview ${theme.id}`} aria-hidden>
              <span className="preview-bar" />
              <span className="preview-window"><span className="preview-line" /><span className="preview-button" /></span>
            </span>
            <span className="theme-words">
              <strong>{theme.name}</strong>
              <span className="muted">{theme.description}</span>
            </span>
          </label>
        ))}
      </div>
      {error && <p className="error" role="alert">Could not save the theme: {error}</p>}
    </section>
  );
}
