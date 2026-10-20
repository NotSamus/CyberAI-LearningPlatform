import type { Metadata } from "next";
import { cookies } from "next/headers";
import TopBar from "@/components/TopBar";
import { MODE_COOKIE, THEME_COOKIE, isMode, isTheme } from "@/lib/themes";
import "./globals.css";
import "./styles/teach.css";
import "./styles/learn.css";
import "./styles/themes.css";

export const metadata: Metadata = {
  title: "cyberAI Platform",
  description: "Lessons and notebook assignments for cyber security and AI courses",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // The theme (and light or dark) this browser last showed, so the page is drawn in it from the
  // start. The account's own choice comes with /api/me, and the top bar switches to it if it differs.
  const jar = await cookies();
  const saved = jar.get(THEME_COOKIE)?.value;
  const theme = isTheme(saved) && saved !== "standard" ? saved : undefined;
  const savedMode = jar.get(MODE_COOKIE)?.value;
  const mode = isMode(savedMode) && savedMode !== "device" ? savedMode : undefined;
  return (
    <html lang="en" data-theme={theme} data-mode={mode}>
      <body>
        <TopBar />
        {children}
      </body>
    </html>
  );
}
