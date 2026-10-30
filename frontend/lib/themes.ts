// How the site can look: a theme, in its light or its dark version. Each account keeps both choices
// on the server (users.theme and users.color_mode, PUT /api/auth/theme), so they follow the person
// to every device. Cookies in the browser keep them too, only so that a page is drawn in them from
// the first moment (app/layout.tsx reads the cookies). The colours themselves are in
// app/globals.css (Standard) and app/styles/themes.css.

export const THEMES = [
  { id: "standard", name: "Standard", description: "UTEP blue and orange, on white or on charcoal." },
  { id: "halloween", name: "Halloween", description: "Pumpkin orange and purple, on bone white or midnight, with a few bats." },
  { id: "retro", name: "Retro 95", description: "Grey windows on a teal desktop, like a computer from 1995." },
] as const;

// Every theme has a light and a dark version. "device": whichever the device is set to, as it changes.
export const MODES = [
  { id: "device", name: "Match my device" },
  { id: "light", name: "Light" },
  { id: "dark", name: "Dark" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
export type ModeId = (typeof MODES)[number]["id"];

export const THEME_COOKIE = "cyberai_theme";
export const MODE_COOKIE = "cyberai_mode";

export function isTheme(value: unknown): value is ThemeId {
  return THEMES.some((theme) => theme.id === value);
}

export function isMode(value: unknown): value is ModeId {
  return MODES.some((mode) => mode.id === value);
}

// The theme the page is shown in right now.
export function shownTheme(): ThemeId {
  const theme = document.documentElement.dataset.theme;
  return isTheme(theme) ? theme : "standard";
}

// The light or dark choice the page is shown in right now.
export function shownMode(): ModeId {
  const mode = document.documentElement.dataset.mode;
  return isMode(mode) ? mode : "device";
}

// Shows the page in `theme` at once, and remembers it in this browser for the next page.
export function applyTheme(theme: ThemeId): void {
  const root = document.documentElement;
  if (theme === "standard") delete root.dataset.theme;
  else root.dataset.theme = theme;
  remember(THEME_COOKIE, theme);
}

// The same for light or dark. No data-mode at all: as the device is set (the CSS asks the device).
export function applyMode(mode: ModeId): void {
  const root = document.documentElement;
  if (mode === "device") delete root.dataset.mode;
  else root.dataset.mode = mode;
  remember(MODE_COOKIE, mode);
}

function remember(cookie: string, value: string): void {
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${cookie}=${value}; path=/; max-age=31536000; samesite=lax${secure}`;
}
