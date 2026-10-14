import type { Metadata } from "next";
import { cookies } from "next/headers";
import TopBar from "@/components/TopBar";
import { THEME_COOKIE, isTheme } from "@/lib/themes";
import "./globals.css";
import "./styles/teach.css";
import "./styles/learn.css";
import "./styles/themes.css";

export const metadata: Metadata = {
  title: "cyberAI Platform",
  description: "Lessons and notebook assignments for cyber security and AI courses",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // The theme this browser last showed, so the page is drawn in it from the start. The account's
  // own choice comes with /api/me, and the top bar switches to it if it is another one.
  const saved = (await cookies()).get(THEME_COOKIE)?.value;
  const theme = isTheme(saved) && saved !== "standard" ? saved : undefined;
  return (
    <html lang="en" data-theme={theme}>
      <body>
        <TopBar />
        {children}
      </body>
    </html>
  );
}
