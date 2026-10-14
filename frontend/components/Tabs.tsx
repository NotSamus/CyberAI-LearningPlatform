"use client";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export type Tab = {
  href: string;
  label: string;
  icon?: LucideIcon;
  count?: number;             // shown next to the label, e.g. how many submissions wait
  exact?: boolean;            // active only on this very page, not on the pages under it
};

// "area": the sections of Teach or Admin, in a strip under the bar. "item": the views of one thing
// (a lesson's Write and Progress), under its title.
export default function Tabs({ tabs, kind = "item", label }: { tabs: Tab[]; kind?: "area" | "item"; label: string }) {
  const path = usePathname();
  const active = (tab: Tab) => (tab.exact ? path === tab.href : path === tab.href || path.startsWith(`${tab.href}/`));
  const links = tabs.map((tab) => {
    const Icon = tab.icon;
    const here = active(tab);
    return (
      <Link key={tab.href} href={tab.href} className={here ? "active" : ""} aria-current={here ? "page" : undefined}>
        {Icon && <Icon aria-hidden />}
        {tab.label}
        {tab.count !== undefined && tab.count > 0 && <span className="chip">{tab.count}</span>}
      </Link>
    );
  });
  return kind === "area"
    ? <div className="area-tabs"><nav aria-label={label}>{links}</nav></div>
    : <nav className="item-tabs" aria-label={label}>{links}</nav>;
}
