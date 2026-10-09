"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { sectionsFor } from "@/lib/sections";
import { useMe } from "@/lib/useMe";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const path = usePathname();
  return (
    <div className="settings">
      <nav className="settings-nav" aria-label="Settings">
        <p className="muted">Settings</p>
        {me && sectionsFor(me).map((section) => (
          <Link key={section.href} href={section.href} className={path === section.href || path.startsWith(`${section.href}/`) ? "active" : ""}>
            {section.label}
          </Link>
        ))}
      </nav>
      <main className="settings-body">{children}</main>
    </div>
  );
}
