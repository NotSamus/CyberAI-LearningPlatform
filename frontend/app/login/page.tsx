"use client";
import { useState } from "react";
import { api, endHubSession, type Me } from "@/lib/api";

// Where to go after logging in: only a page on this site. `next` is read the way the browser will
// read it, because many strings that look like a path are another site to a browser ("//host",
// "/\host", and "/<tab>/host", whose tab the browser drops). Anything else goes to Home.
function safeNext(next: string | null): string {
  if (!next) return "/";
  try {
    const url = new URL(next, window.location.origin);
    return url.origin === window.location.origin ? url.pathname + url.search + url.hash : "/";
  } catch {
    return "/";
  }
}

// Where to go when no page was asked for: teachers and admins start on Teach, students on Home.
// Asked of the server once the login has succeeded; Home if that fails.
async function landing(): Promise<string> {
  const me = await api<Me>("/me").catch(() => null);
  return me?.can_teach ? "/teach" : "/";
}

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const asked = new URLSearchParams(window.location.search).get("next");
      const next = asked === null ? await landing() : safeNext(asked);
      // Someone else may have used this browser without logging out: drop their JupyterHub session.
      // Not when JupyterHub itself sent us here (/oauth/authorize): then it has no session to drop,
      // and logging it out now would break the sign-in it is in the middle of.
      if (!next.startsWith("/oauth/")) await endHubSession();
      // A full page load, not a client-side route change: /oauth/authorize is served by the backend.
      window.location.assign(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <main className="login">
      {/* The navy of the bar goes on down the page, with the card for logging in over its edge */}
      <div className="login-band">
        <p className="eyebrow">Cyber security and AI</p>
        <h1>Log in</h1>
        <p>Lessons, knowledge checks and notebook assignments for your courses.</p>
      </div>
      <div className="login-card">
      {/* method="post": sent before the page's script has loaded, the form must never put the
          password in the address */}
      <form method="post" onSubmit={submit}>
        <label>
          Username
          <input
            name="username" autoComplete="username" autoCapitalize="none" autoFocus required
            value={username} onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            name="password" type="password" autoComplete="current-password" required
            value={password} onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button type="submit" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
        {error && <p className="error" role="alert">{error}</p>}
      </form>
      <p className="muted">
        Accounts are made by the platform&apos;s admins. Forgot your password? Ask your teacher or an
        admin for a new one.
      </p>
      </div>
    </main>
  );
}
