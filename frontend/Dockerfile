# Build context is frontend/ (see docker-compose.yml).
FROM node:24-trixie-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-trixie-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Baked in at build time — Next.js inlines NEXT_PUBLIC_* into the client
# bundle, so this must be set for the browser to reach the backend. The same value
# also fixes the Content-Security-Policy `connect-src` (next.config.ts).
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

FROM node:24-trixie-slim AS runner
WORKDIR /app
# HOSTNAME: Docker sets it to the container id, and the Next.js standalone server would then listen on that name only; bind every interface so
# the published port and the health check reach it.
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000 NEXT_TELEMETRY_DISABLED=1

# Code and assets stay owned by root, so the unprivileged runtime user cannot rewrite the server it runs. The one writable place is Next's runtime cache.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Hardening of a runtime image: not writable by the service user; no browser source maps (they publish the original source layout); no package
# manager (npm and its bundled dependencies are not needed to run `node server.js`); no setuid binaries.
RUN chmod -R go-w /app \
    && mkdir -p /app/.next/cache \
    && chown node:node /app/.next/cache \
    && find /app -name '*.map' -delete \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx
# (`upgrade` picks up Debian security fixes published after the base image was built.)
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*
RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

# the image's built-in unprivileged user (uid 1000)
USER node

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/login').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]
CMD ["node", "server.js"]
