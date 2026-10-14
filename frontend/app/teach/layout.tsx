"use client";
import { BookOpen, LayoutDashboard, Lock, Megaphone, NotebookPen, School } from "lucide-react";
import Link from "next/link";
import EmptyState from "@/components/EmptyState";
import Tabs from "@/components/Tabs";
import { useMe } from "@/lib/useMe";

// Teach: everything a teacher (or an admin) does, in five sections. Nothing shows until the account
// is known; a student gets a short message. Hiding it is only tidiness: every page here gets its data
// from /api/teach, which the server refuses to anyone who cannot teach.
export default function TeachLayout({ children }: { children: React.ReactNode }) {
  const me = useMe();
  if (!me) return null;
  if (!me.can_teach) {
    return (
      <main className="area-page">
        <EmptyState icon={Lock} title="This area is for teachers" action={<Link href="/" className="button">Go to Home</Link>}>
          Your lessons and assignments are on Home.
        </EmptyState>
      </main>
    );
  }
  return (
    <>
      <Tabs
        kind="area" label="Teach"
        tabs={[
          { href: "/teach", label: "Overview", icon: LayoutDashboard, exact: true },
          { href: "/teach/courses", label: "Courses", icon: School },
          { href: "/teach/lessons", label: "Lessons", icon: BookOpen },
          { href: "/teach/assignments", label: "Assignments", icon: NotebookPen },
          { href: "/teach/announcements", label: "Announcements", icon: Megaphone },
        ]}
      />
      <main className="area-page">{children}</main>
    </>
  );
}
