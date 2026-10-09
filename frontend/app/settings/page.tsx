"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { sectionsFor } from "@/lib/sections";
import { useMe } from "@/lib/useMe";

// /settings itself has nothing to show: go to the first section this account has.
export default function SettingsIndex() {
  const me = useMe();
  const router = useRouter();
  useEffect(() => {
    if (me) router.replace(sectionsFor(me)[0]?.href ?? "/");
  }, [me, router]);
  return <p className="muted">Loading…</p>;
}
