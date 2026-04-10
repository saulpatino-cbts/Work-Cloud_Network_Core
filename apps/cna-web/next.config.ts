import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  serverExternalPackages: ["@prisma/client"],
  outputFileTracingRoot: path.join(__dirname, "../.."),
  experimental: {
    serverActions: {
      // Allow large document uploads (up to 50 MB) via Server Actions.
      bodySizeLimit: "52mb",
    },
  },
};

export default nextConfig;
