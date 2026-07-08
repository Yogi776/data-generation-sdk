/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export so the FastAPI backend can serve the UI from a pip install
  // with no Node runtime required in production.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // API base is same-origin by default (FastAPI serves both UI and API).
  // Override for local dev against a separately-running backend.
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "",
  },
};

export default nextConfig;
