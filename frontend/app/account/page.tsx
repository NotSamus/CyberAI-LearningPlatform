"use client";
import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import { MODES, THEMES, applyMode, applyTheme, isMode, isTheme, shownMode, shownTheme, type ModeId, type ThemeId } from "@/lib/themes";
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
        description={me && <>Logged in as <strong>{me.name}</strong>{me.name !== me.username && ` (${me.username})`}, {me.is_admin ? `${me.role} and admin` : me.role}.</>}
      />
      {error && <p className="error" role="alert">{error}</p>}
      {changed && (
        <p className="notice" role="status">
          Your password is changed. You stay logged in here; every other device that was logged in to this account has been logged out.
        </p>
      )}

      <Appearance
        savedTheme={me && isTheme(me.theme) ? me.theme : null}
        savedMode={me ? (isMode(me.mode) ? me.mode : "device") : null}
      />

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

// The theme of this account, and light or dark. A choice changes the page at once and is then
// saved on the server; if saving fails, the page goes back to what it showed before.
function Appearance({ savedTheme, savedMode }: { savedTheme: ThemeId | null; savedMode: ModeId | null }) {
  const [theme, setTheme] = useState<ThemeId | null>(null);
  const [mode, setMode] = useState<ModeId | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const deviceDark = useSyncExternalStore(watchDeviceDark, isDeviceDark, () => false);
  useEffect(() => { if (savedTheme) setTheme(savedTheme); }, [savedTheme]);
  useEffect(() => { if (savedMode) setMode(savedMode); }, [savedMode]);
  // The pictures show each theme as it would look now: in its light or its dark version
  const dark = mode === "dark" || (mode !== "light" && deviceDark);

  async function choose(change: { theme?: ThemeId; mode?: ModeId }) {
    const before = { theme: shownTheme(), mode: shownMode() };
    setError("");
    if (change.theme) { setTheme(change.theme); applyTheme(change.theme); }
    if (change.mode) { setMode(change.mode); applyMode(change.mode); }
    setBusy(true);
    try {
      await api("/auth/theme", { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(change) });
    } catch (e) {
      setTheme(before.theme);
      applyTheme(before.theme);
      setMode(before.mode);
      applyMode(before.mode);
      setError(message(e));
    }
    setBusy(false);
  }

  const ready = theme !== null && mode !== null;
  return (
    <section className="card">
      <h2>Appearance</h2>
      <p className="muted">How the site looks for you, on every device you log in on.</p>
      <div className="theme-choices" role="radiogroup" aria-label="Theme">
        {THEMES.map((t) => (
          <label key={t.id} className={`theme-choice ${theme === t.id ? "chosen" : ""}`}>
            <input
              type="radio" name="theme" value={t.id} checked={theme === t.id}
              disabled={busy || !ready} onChange={() => choose({ theme: t.id })}
            />
            {/* A small picture of the theme, in its own colours whichever theme is shown now */}
            <span className={`theme-preview ${t.id} ${dark ? "dark" : ""}`} aria-hidden>
              <span className="preview-bar" />
              <span className="preview-window"><span className="preview-line" /><span className="preview-button" /></span>
            </span>
            <span className="theme-words">
              <strong>{t.name}</strong>
              <span className="muted">{t.description}</span>
            </span>
          </label>
        ))}
      </div>
      <fieldset className="mode-choices">
        <legend>Light or dark</legend>
        <div className="mode-row">
          {MODES.map((m) => {
            const Icon = m.id === "light" ? Sun : m.id === "dark" ? Moon : Monitor;
            return (
              <label key={m.id} className={`mode-choice ${mode === m.id ? "chosen" : ""}`}>
                <input
                  type="radio" name="mode" value={m.id} checked={mode === m.id}
                  disabled={busy || !ready} onChange={() => choose({ mode: m.id })}
                />
                <Icon aria-hidden />{m.name}
              </label>
            );
          })}
        </div>
      </fieldset>
      {error && <p className="error" role="alert">Could not save your choice: {error}</p>}
    </section>
  );
}

// Whether the device is set to dark, kept up to date when that changes (for the pictures above)
const DARK_QUERY = "(prefers-color-scheme: dark)";
function watchDeviceDark(changed: () => void): () => void {
  const query = window.matchMedia(DARK_QUERY);
  query.addEventListener("change", changed);
  return () => query.removeEventListener("change", changed);
}
function isDeviceDark(): boolean {
  return window.matchMedia(DARK_QUERY).matches;
}
