"use client";
import Link from "next/link";
import { api, endHubSession } from "@/lib/api";
import { sectionsFor } from "@/lib/sections";
import { useMe } from "@/lib/useMe";

export default function UserBadge() {
  const me = useMe();

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    await endHubSession();      // so the next person on this computer cannot reach this account's notebooks
    window.location.assign("/login");
  }

  if (!me) return null;
  return (
    <span className="user">
      <span className="muted">{me.name}</span>
      {sectionsFor(me).length > 0 && <Link href="/settings" className="button secondary">Settings</Link>}
      <button className="secondary" onClick={logout}>Log out</button>
    </span>
  );
}
