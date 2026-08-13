import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for a lean Docker image (docs/DEPLOYMENT.md) — bundles
  // only the production node_modules subset the build actually needs.
  output: "standalone",
};

export default nextConfig;
