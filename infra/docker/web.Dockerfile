# Web image (Next.js). STATUS: built and smoke-tested in GitHub Actions CI (2026-11-22).
# Assumes apps/web uses `output: "standalone"` in next.config. Build from repo root:
#   docker build -f infra/docker/web.Dockerfile -t dml-web .
FROM node:22-slim AS deps
RUN corepack enable
WORKDIR /srv/app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY apps/web/package.json apps/web/package.json
COPY packages/ packages/
RUN pnpm install --frozen-lockfile || pnpm install

FROM deps AS build
COPY apps/web apps/web
# Next.js bakes the /api/v1 rewrite target into the build, so it must be known at BUILD time
# (override with --build-arg API_INTERNAL_URL=... when the API is not reachable as http://api:8000).
ARG API_INTERNAL_URL=http://api:8000
ENV NEXT_TELEMETRY_DISABLED=1 API_INTERNAL_URL=${API_INTERNAL_URL}
RUN pnpm --filter ./apps/web build

FROM node:22-slim AS run
WORKDIR /srv/app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN useradd --create-home --uid 10001 webuser
COPY --from=build --chown=webuser /srv/app/apps/web/.next/standalone ./
COPY --from=build --chown=webuser /srv/app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=webuser /srv/app/apps/web/public ./apps/web/public
# The /docs pages render the repository's real markdown (docs/internal is excluded by .dockerignore).
COPY --chown=webuser docs ./docs
ENV DOCS_ROOT=/srv/app/docs
USER webuser
EXPOSE 3000
# API_INTERNAL_URL is used by Next rewrites to proxy /api/v1/* to the API container (same-origin for the browser).
ENV API_INTERNAL_URL=http://api:8000
CMD ["node", "apps/web/server.js"]
