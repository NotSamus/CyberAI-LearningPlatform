"use client";
import { useEffect, useState } from "react";
import { api, HUB_ORIGIN } from "@/lib/api";

const HUB_ADMIN = `${HUB_ORIGIN}/hub/admin`;

export default function HubSettings() {
  // Shown to admins only. JupyterHub checks its own admins too, whatever this page does.
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/admin/users").then(() => setAllowed(true)).catch((e) => { setError(e.message); setAllowed(false); });
  }, []);

  if (allowed === null) return <><h1>JupyterHub</h1><p className="muted">Loading…</p></>;
  if (!allowed) return <><h1>JupyterHub</h1><p className="error" role="alert">{error}</p></>;

  return (
    <>
      <h1>JupyterHub</h1>
      <p className="muted">
        Use this panel to see and stop notebook servers. Create accounts under Accounts, not with “Add Users” here:
        an account added only in JupyterHub cannot log in. “Shutdown Hub” stops every notebook for everyone.{" "}
        <a href={HUB_ADMIN} target="_blank" rel="noopener">Open in a new tab</a>
      </p>
      <iframe className="hub-admin" src={HUB_ADMIN} title="JupyterHub admin" />
    </>
  );
}
