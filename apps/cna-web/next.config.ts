import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  // Trust the Azure Front Door / Container Apps reverse proxy headers.
  // Required for NextAuth to construct correct callback URLs.
  serverExternalPackages: ["@prisma/client"],
  // Pin file-tracing root to the repo root so the standalone build doesn't
  // walk up to the OS user directory when multiple lockfiles are detected.
  outputFileTracingRoot: path.join(__dirname, "../.."),
};

export default nextConfig;
