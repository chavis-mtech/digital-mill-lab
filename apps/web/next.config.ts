import type { NextConfig } from "next";
import path from "node:path";

/**
 * Same-origin API proxy (the build plan §3): the browser only ever calls `/api/v1/*` on the web origin;
 * Next rewrites it to the FastAPI service. Target resolution:
 *   API_INTERNAL_URL (e.g. http://api:8000 in docker-compose)  >  http://127.0.0.1:${API_PORT:-8000}
 * NOTE: rewrites are baked into the build manifest, so set API_PORT / API_INTERNAL_URL at `next build` time too.
 */
const apiTarget = (process.env.API_INTERNAL_URL ?? `http://127.0.0.1:${process.env.API_PORT ?? "8000"}`).replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),
  reactStrictMode: true,
  poweredByHeader: false,
  typedRoutes: false,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiTarget}/api/v1/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
