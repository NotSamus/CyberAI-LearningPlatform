// Merge into your Next.js config.
const HUB_ORIGIN = process.env.NEXT_PUBLIC_HUB_ORIGIN ?? "https://hub.school.example";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Frames may show the hub, plus the platform itself: the notebook iframe's login passes
          // through this origin's /oauth/authorize. Nobody else may frame the platform.
          { key: "Content-Security-Policy", value: `frame-src 'self' ${HUB_ORIGIN}; frame-ancestors 'self'` },
        ],
      },
    ];
  },
  // Local development only: forward API + OAuth routes to uvicorn (Caddy does this in production)
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    return [
      { source: "/api/:path*", destination: "http://localhost:8000/api/:path*" },
      { source: "/oauth/:path*", destination: "http://localhost:8000/oauth/:path*" },
    ];
  },
};

export default nextConfig;
