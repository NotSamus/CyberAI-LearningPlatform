"use client";
import { Ellipsis, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

export type MenuItem = {
  label: string;
  icon?: LucideIcon;
  href?: string;              // a link, or else
  download?: boolean;         // with href: a file the server sends (grades as CSV), so a plain link rather than a page of the site
  onSelect?: () => void;      // an action
  danger?: boolean;           // deleting and the like: in red, after a line
  disabled?: boolean;
};

// A button that opens a short list of actions: the "more" menu (⋯) for what is rare or cannot be
// undone, and the menu under your name. Closes on a choice, a click elsewhere, or Escape.
export default function Menu({ label, items, trigger, triggerClass = "icon" }: {
  label: string;                  // says what the button opens, for screen readers and as its tooltip
  items: MenuItem[];
  trigger?: React.ReactNode;      // what the button shows; three dots when left out
  triggerClass?: string;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement | null>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", key);
    box.current?.querySelector<HTMLElement>("[role=menuitem]:not(:disabled)")?.focus();
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", key);
    };
  }, [open]);

  // Up and down move between the entries.
  function move(e: React.KeyboardEvent) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const entries = Array.from(box.current?.querySelectorAll<HTMLElement>("[role=menuitem]:not(:disabled)") ?? []);
    const here = entries.indexOf(document.activeElement as HTMLElement);
    entries[(here + (e.key === "ArrowDown" ? 1 : entries.length - 1)) % entries.length]?.focus();
  }

  return (
    <div className="menu" ref={box}>
      <button
        type="button" className={triggerClass} aria-label={label} title={label}
        aria-haspopup="menu" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}
      >
        {trigger ?? <Ellipsis aria-hidden />}
      </button>
      {open && (
        <ul className="menu-list" role="menu" id={id} onKeyDown={move}>
          {items.map((item, n) => {
            const Icon = item.icon;
            const inner = <>{Icon && <Icon aria-hidden />}{item.label}</>;
            return (
              <li key={item.label} role="none">
                {item.danger && n > 0 && <hr />}
                {item.href && item.download ? (
                  <a href={item.href} download role="menuitem" className={item.danger ? "danger" : ""} onClick={() => setOpen(false)}>{inner}</a>
                ) : item.href ? (
                  <Link href={item.href} role="menuitem" className={item.danger ? "danger" : ""} onClick={() => setOpen(false)}>{inner}</Link>
                ) : (
                  <button
                    type="button" role="menuitem" className={item.danger ? "danger" : ""} disabled={item.disabled}
                    onClick={() => { setOpen(false); item.onSelect?.(); }}
                  >
                    {inner}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
