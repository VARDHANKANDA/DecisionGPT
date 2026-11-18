import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

// The browser may only talk to this site and to the API. A script injected into a page (XSS) could still read the session token from
// localStorage, but with connect-src limited to these origins it could not send it anywhere else. 'unsafe-inline' for scripts is required by
// Next's inline bootstrap without a per-request nonce (nonce-based CSP needs dynamic rendering for every page; see
// docs/PRODUCTION_SECURITY_REVIEW.md for what this does and does not protect against).
function apiOrigin(): string {
  try {
    return new URL(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1").origin;
  } catch {
    return "";
  }
}

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin()}${isDev ? " ws: wss:" : ""}`.trim(),
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  // voice input uses the microphone of this origin only; nothing else is requested
  { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=(), payment=()" },
  // honoured by browsers only over https; harmless over http. The TLS-terminating proxy should send it as well (deploy/Caddyfile.example).
  ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]),
];

const nextConfig: NextConfig = {
  // Standalone output for a lean Docker image (docs/DEPLOYMENT.md) — bundles
  // only the production node_modules subset the build actually needs.
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  // Pages that were folded into the everyday navigation keep working from old links/bookmarks.
  async redirects() {
    return [
      { source: "/insights", destination: "/analytics", permanent: false },
      { source: "/data/numbers", destination: "/analytics", permanent: false },
    ];
  },
};

export default nextConfig;
