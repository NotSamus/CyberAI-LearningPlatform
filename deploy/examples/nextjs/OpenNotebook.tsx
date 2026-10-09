"use client";
// Drop into your Next.js app (e.g. app/assignments/[id]/OpenNotebook.tsx).
// Same-origin call to FastAPI (/api is routed by Caddy; in dev use a Next.js rewrite), so no CORS.
import { useState } from "react";

type Launch = { ready: boolean; profile: "cpu" | "gpu"; url: string };

export default function OpenNotebook({ assignmentId }: { assignmentId: string }) {
  const [state, setState] = useState<"idle" | "starting" | "open" | "error">("idle");
  const [launch, setLaunch] = useState<Launch | null>(null);
  const [error, setError] = useState("");

  async function open() {
    setState("starting");
    setError("");
    try {
      const res = await fetch(`/api/assignments/${assignmentId}/launch`, {
        method: "POST",
        credentials: "same-origin", // sends the platform session cookie
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? "Could not start the notebook.");
      setLaunch(body);
      setState("open");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setState("error");
    }
  }

  if (state === "open" && launch) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 64px)" }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", padding: 8 }}>
          <span>{launch.profile === "gpu" ? "GPU environment" : "Standard environment"}</span>
          <a href={launch.url} target="_blank" rel="noopener">Open in a new tab</a>
        </div>
        <iframe
          src={launch.url}
          title="Jupyter notebook"
          style={{ flex: 1, width: "100%", border: 0 }}
          // Clipboard for copy/paste in cells. Do NOT add a sandbox attribute:
          // JupyterLab needs its own same-origin storage, cookies and WebSockets.
          allow="clipboard-read; clipboard-write; fullscreen"
        />
      </div>
    );
  }

  return (
    <div>
      <button onClick={open} disabled={state === "starting"}>
        {state === "starting" ? "Starting your environment (up to a minute)…" : "Open Notebook"}
      </button>
      {state === "error" && <p role="alert">{error}</p>}
    </div>
  );
}
