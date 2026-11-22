import type { NextConfig } from "next";
import fs from "node:fs";
import path from "node:path";

/**
 * Same-origin API proxy (the build plan §3): the browser only ever calls `/api/v1/*` on the web origin;
 * Next rewrites it to the FastAPI service. Target resolution:
 *   API_INTERNAL_URL (e.g. http://api:8000 in docker-compose)  >  http://127.0.0.1:${API_PORT:-8000}
 * NOTE: rewrites are baked into the build manifest, so set API_PORT / API_INTERNAL_URL at `next build` time too.
 */
const apiTarget = (process.env.API_INTERNAL_URL ?? `http://127.0.0.1:${process.env.API_PORT ?? "8000"}`).replace(/\/$/, "");

// Documentation files the /docs pages may render (everything under docs/ except the private `internal` folder).
const docsDir = path.join(import.meta.dirname, "../../docs");
const docsIncludes = fs.existsSync(docsDir)
  ? [
      "../../docs/*.md",
      ...fs.readdirSync(docsDir, { withFileTypes: true }).filter((d) => d.isDirectory() && d.name !== "internal").map((d) => `../../docs/${d.name}/**/*`),
    ]
  : [];

// On Vercel the platform builds its own serverless bundles; `standalone` is for the Docker image only.
const onVercel = Boolean(process.env.VERCEL);

const nextConfig: NextConfig = {
  output: onVercel ? undefined : "standalone",
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),
  // The /docs pages read the repository's markdown at request time (features/docs/load.ts opts out of tracing), so on a
  // serverless platform those files must be included in the function bundle explicitly. Folders are listed one by one so
  // that `docs/internal` (private notes, git-ignored) can never be matched, even in a local checkout that has it.
  outputFileTracingIncludes: { "/docs/*": docsIncludes, "/docs/**/*": docsIncludes },
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
