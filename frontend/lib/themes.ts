// How the site can look. Each account keeps its choice on the server (users.theme, PUT
// /api/auth/theme), so it follows the person to every device. A cookie in the browser keeps it too,
// only so that a page is drawn in it from the first moment (app/layout.tsx reads the cookie).
// The colours themselves are in app/styles/themes.css.

export const THEMES = [
  { id: "standard", name: "Standard", description: "Navy and white, light or dark as your device is set." },
  { id: "halloween", name: "Halloween", description: "Pumpkin orange on midnight purple, with a few bats." },
  { id: "retro", name: "Retro 95", description: "Grey windows on a teal desktop, like a computer from 1995." },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

export const THEME_COOKIE = "cyberai_theme";

export function isTheme(value: unknown): value is ThemeId {
  return THEMES.some((theme) => theme.id === value);
}

// The theme the page is shown in right now.
export function shownTheme(): ThemeId {
  const theme = document.documentElement.dataset.theme;
  return isTheme(theme) ? theme : "standard";
}

// Shows the page in `theme` at once, and remembers it in this browser for the next page.
export function applyTheme(theme: ThemeId): void {
  const root = document.documentElement;
  if (theme === "standard") delete root.dataset.theme;
  else root.dataset.theme = theme;
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=31536000; samesite=lax${secure}`;
}
