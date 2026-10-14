"use client";
import { ChevronDown, GraduationCap, House, LogOut, Shield, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import Brand from "@/components/Brand";
import Menu from "@/components/Menu";
import { api, endHubSession } from "@/lib/api";
import { applyTheme, isTheme, shownTheme } from "@/lib/themes";
import { useMe } from "@/lib/useMe";

// The first letters of the first and the last word of a name. Words that do not start with a
// letter or a digit, such as "(test)", are skipped.
function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter((word) => /^[\p{L}\p{N}]/u.test(word));
  return ((words[0]?.[0] ?? "") + (words.length > 1 ? words[words.length - 1][0] : "")).toUpperCase() || "?";
}

// The navy bar at the top: the logo, the areas this account has (Home for everyone, Teach for
// teachers and admins, Admin for admins), and the menu under the person's name. Showing a link is
// only tidiness: every page's data comes from the server, which checks the account each time.
export default function TopBar() {
  const me = useMe();
  const path = usePathname();

  // The account's own theme, once it is known: this browser may have shown another one last time.
  useEffect(() => {
    if (me && isTheme(me.theme) && me.theme !== shownTheme()) applyTheme(me.theme);
  }, [me]);

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    await endHubSession();      // so the next person on this computer cannot reach this account's notebooks
    window.location.assign("/login");
  }

  const elsewhere = ["/teach", "/admin", "/account"].some((area) => path === area || path.startsWith(`${area}/`));
  const areas = me ? [
    { href: "/", label: "Home", icon: House, here: !elsewhere },
    ...(me.can_teach ? [{ href: "/teach", label: "Teach", icon: GraduationCap, here: path === "/teach" || path.startsWith("/teach/") }] : []),
    ...(me.is_admin ? [{ href: "/admin", label: "Admin", icon: Shield, here: path === "/admin" || path.startsWith("/admin/") }] : []),
  ] : [];

  return (
    <header className="topbar">
      <Link href="/" className="brand" aria-label="cyberAI Platform, home"><Brand /></Link>
      {me && (
        <nav className="topnav" aria-label="Areas">
          {areas.map(({ href, label, icon: Icon, here }) => (
            <Link key={href} href={href} className={here ? "active" : ""} aria-current={here ? "page" : undefined}>
              <Icon aria-hidden />{label}
            </Link>
          ))}
        </nav>
      )}
      <span className="spacer" />
      {me && (
        <Menu
          label={`${me.name}: your account`} triggerClass="who"
          trigger={<><span className="avatar" aria-hidden>{initials(me.name)}</span>{me.name}<ChevronDown aria-hidden /></>}
          items={[
            { label: "My account", icon: UserRound, href: "/account" },
            { label: "Log out", icon: LogOut, onSelect: logout },
          ]}
        />
      )}
    </header>
  );
}
