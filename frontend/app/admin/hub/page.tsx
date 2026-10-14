"use client";
import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { api, HUB_ORIGIN } from "@/lib/api";
import { message } from "@/lib/errors";

const HUB_ADMIN = `${HUB_ORIGIN}/hub/admin`;

export default function HubPage() {
  // Shown to admins only. JupyterHub checks its own admins too, whatever this page does.
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/admin/users").then(() => setAllowed(true)).catch((e) => { setError(message(e)); setAllowed(false); });
  }, []);

  const header = (
    <PageHeader
      title="JupyterHub"
      description={
        <>
          See and stop notebook servers here. Create accounts under Accounts, not with “Add Users” here: an account
          added only in JupyterHub cannot log in. “Shutdown Hub” stops every notebook for everyone.
        </>
      }
      actions={allowed && <a href={HUB_ADMIN} target="_blank" rel="noopener" className="button secondary"><ExternalLink aria-hidden />Open in a new tab</a>}
    />
  );

  if (allowed === null) return <>{header}<p className="muted">Loading…</p></>;
  if (!allowed) return <>{header}<p className="error" role="alert">{error}</p></>;
  return <>{header}<iframe className="hub-admin" src={HUB_ADMIN} title="JupyterHub admin" /></>;
}
