import type { Metadata } from "next";
import Link from "next/link";
import UserBadge from "@/components/UserBadge";
import "./globals.css";

export const metadata: Metadata = {
  title: "cyberAI Platform",
  description: "Coding assignments with Jupyter notebooks",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">cyberAI Platform</Link>
          <UserBadge />
        </header>
        {children}
      </body>
    </html>
  );
}
