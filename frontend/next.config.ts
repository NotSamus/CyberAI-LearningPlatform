import type { NextConfig } from "next";

const HUB_ORIGIN = process.env.NEXT_PUBLIC_HUB_ORIGIN ?? "http://localhost:8081";
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8003";

// `./dev.sh --lan` serves the dev site at this computer's network address instead of localhost.
const DEV_HOST = process.env.DEV_HOST ?? "localhost";

const nextConfig: NextConfig = {
  output: "standalone",
  // `next dev` only: browsers that open the site at that address may load its scripts and live updates.
  allowedDevOrigins: DEV_HOST === "localhost" ? undefined : [DEV_HOST],
  // The project root is this folder. Without this, a stray lockfile higher up (e.g. the repo
  // root) makes Next.js guess the wrong root and lay out the standalone server incorrectly.
  outputFileTracingRoot: __dirname,
  experimental: {
    // Local development only: `next dev` forwards /api to the backend (rewrites below) and takes in
    // at most this much of a request. The default, 10 MB, is exactly the notebook limit, so an
    // upload of that size plus its form fields would stall. In production Caddy sends /api
    // straight to the backend and this does not apply.
    middlewareClientMaxBodySize: "12mb",
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Frames may show the hub, plus the platform itself: the notebook iframe's login passes
          // through this origin's /oauth/authorize. Videos in lessons are YouTube's player without
          // its cookies. Nobody else may frame the platform.
          { key: "Content-Security-Policy", value: `frame-src 'self' ${HUB_ORIGIN} https://www.youtube-nocookie.com; frame-ancestors 'self'` },
        ],
      },
    ];
  },
  // Teaching and accounts used to live under /settings. Old links and bookmarks are sent on to
  // where each page is now, with their query string. Temporary (307), so the old paths stay free.
  // "/:path*" also matches nothing, so each rule covers its list page too. /settings itself is a
  // page (app/settings/page.tsx): where it sends you depends on who you are.
  async redirects() {
    const moved = (from: string, to: string) => ({ source: from, destination: to, permanent: false });
    return [
      moved("/settings/lessons/:path*", "/teach/lessons/:path*"),
      moved("/settings/assignments/:path*", "/teach/assignments/:path*"),
      moved("/settings/courses/:path*", "/teach/courses/:path*"),
      moved("/settings/announcements/:path*", "/teach/announcements/:path*"),
      moved("/settings/accounts", "/admin/accounts"),
      moved("/settings/hub", "/admin/hub"),
      moved("/settings/account", "/account"),
    ];
  },
  // Local development: forward API + OAuth routes to uvicorn. In production Caddy routes
  // these paths to the backend before they ever reach Next.js.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/oauth/:path*", destination: `${BACKEND}/oauth/:path*` },
    ];
  },
};

export default nextConfig;
