import type { NextConfig } from "next";
import path from "path";

const securityHeaders = [
  // Prevent clickjacking
  { key: "X-Frame-Options", value: "DENY" },
  // Prevent MIME-type sniffing
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Force HTTPS (1 year, includeSubDomains)
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  // Restrict referrer to same-origin for external requests
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Disable browser features not used by this app
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  // Content Security Policy — restrictive baseline for a Next.js app behind Azure Front Door.
  // 'unsafe-inline' for styles is required by Tailwind CSS until CSS Modules are used.
  // Nonce-based script CSP is the recommended next upgrade (tracked in TODO.md).
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // Next.js hydration requires inline scripts in dev; in prod use nonce (future work)
      "script-src 'self' 'unsafe-inline'",
      // Tailwind CSS requires inline styles
      "style-src 'self' 'unsafe-inline'",
      // Images from self only (logos are served from /public)
      "img-src 'self' data:",
      // Fonts: self only
      "font-src 'self'",
      // API calls: self + Azure AD (Entra ID) for auth, Azure OpenAI for AI features
      "connect-src 'self' https://login.microsoftonline.com https://*.openai.azure.com",
      // Block all framing
      "frame-ancestors 'none'",
      // Block plugins (Flash, etc.)
      "object-src 'none'",
      // Only HTTPS for all sub-resources
      "upgrade-insecure-requests",
    ].join("; "),
  },
];

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
  async headers() {
    return [
      {
        // Apply security headers to all routes
        source: "/(.*)",
        headers: securityHeaders,
      },
      {
        // Override X-Frame-Options for the print/presentation route (still blocked by CSP frame-ancestors)
        source: "/engagements/:id/presentation/(.*)",
        headers: [{ key: "X-Frame-Options", value: "SAMEORIGIN" }],
      },
    ];
  },
};

export default nextConfig;
