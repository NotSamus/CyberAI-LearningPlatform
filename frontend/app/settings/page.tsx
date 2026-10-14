"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useMe } from "@/lib/useMe";

// Teaching and accounts used to be under /settings. The old pages below it are sent on by the
// redirects in next.config.ts; /settings itself sends teachers to Teach and everyone else to their
// own account.
export default function SettingsIndex() {
  const me = useMe();
  const router = useRouter();
  useEffect(() => {
    if (me) router.replace(me.can_teach ? "/teach" : "/account");
  }, [me, router]);
  return <main className="page"><p className="muted">Loading…</p></main>;
}
