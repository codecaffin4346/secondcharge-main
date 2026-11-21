import type { NextConfig } from "next";

function normalizeBackendUrl(value: string): string {
  const trimmed = value.trim().replace(/\/$/, "");
  if (trimmed.includes("://")) return trimmed;
  if (trimmed.includes(".")) return `https://${trimmed}`;
  return `https://${trimmed}.onrender.com`;
}

const configuredBackend =
  process.env.BACKEND_URL ??
  "secondcharge-api.onrender.com";
const backend = normalizeBackendUrl(configuredBackend);

const nextConfig: NextConfig = {
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
