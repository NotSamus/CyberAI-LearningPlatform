"use client";
import { useState } from "react";
import { api, endHubSession } from "@/lib/api";

// Where to go after logging in. Only a path on this site is accepted: "//host" and "/\host"
// look like paths but browsers treat them as another site.
function safeNext(next: string | null): string {
  return next && /^\/(?![/\\])/.test(next) ? next : "/";
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
      const next = safeNext(new URLSearchParams(window.location.search).get("next"));
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
    <main className="page login">
      <h1>Log in</h1>
      <form onSubmit={submit}>
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
    </main>
  );
}
