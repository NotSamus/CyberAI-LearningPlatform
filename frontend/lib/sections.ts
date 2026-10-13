import type { Me } from "@/lib/api";

// The sections of the Settings page and who sees each one in the menu. Hiding a link is only
// tidiness: every section's data comes from an API route that checks the account on the server.
export type Section = { href: string; label: string; show: (me: Me) => boolean };

export const SECTIONS: Section[] = [
  { href: "/settings/lessons", label: "Lessons", show: (me) => me.can_teach },
  { href: "/settings/assignments", label: "Assignments", show: (me) => me.can_teach },
  { href: "/settings/courses", label: "Courses", show: (me) => me.can_teach },
  { href: "/settings/announcements", label: "Announcements", show: (me) => me.can_teach },
  { href: "/settings/accounts", label: "Accounts", show: (me) => me.is_admin },
  { href: "/settings/hub", label: "JupyterHub", show: (me) => me.is_admin },
  { href: "/settings/account", label: "My account", show: () => true },
];

export function sectionsFor(me: Me): Section[] {
  return SECTIONS.filter((section) => section.show(me));
}
