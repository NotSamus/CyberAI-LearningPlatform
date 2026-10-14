"use client";
import { Lock, Server, Users } from "lucide-react";
import Link from "next/link";
import EmptyState from "@/components/EmptyState";
import Tabs from "@/components/Tabs";
import { useMe } from "@/lib/useMe";

// Admin: the accounts of the platform, and JupyterHub's own panel. Shown to admins only; the
// server refuses /api/admin to everyone else, and JupyterHub checks its own admins.
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const me = useMe();
  if (!me) return null;
  if (!me.is_admin) {
    return (
      <main className="area-page">
        <EmptyState icon={Lock} title="This area is for admins" action={<Link href="/" className="button">Go to Home</Link>}>
          Accounts are added and changed by an admin of the platform.
        </EmptyState>
      </main>
    );
  }
  return (
    <>
      <Tabs
        kind="area" label="Admin"
        tabs={[
          { href: "/admin/accounts", label: "Accounts", icon: Users },
          { href: "/admin/hub", label: "JupyterHub", icon: Server },
        ]}
      />
      <main className="area-page">{children}</main>
    </>
  );
}
