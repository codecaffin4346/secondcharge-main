import type { NextConfig } from "next";

const configuredBackend =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "https://secondcharge-api.onrender.com";
const backend = configuredBackend.includes("://") ? configuredBackend : `https://${configuredBackend}`;

const nextConfig: NextConfig = {
  outputFileTracingRoot: process.cwd(),
  // Forward API calls to FastAPI so the whole app is served from one address.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
