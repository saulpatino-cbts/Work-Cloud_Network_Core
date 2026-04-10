import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Auth.js v5 with PrismaAdapter (database sessions) cannot run in Edge Runtime.
// Importing `auth` from "@/lib/auth" here would instantiate PrismaClient in
// Edge Runtime, which is unsupported and causes UnknownAction errors.
//
// Pattern: use a lightweight cookie-presence check here (UX redirect only).
// Real session validation (DB lookup) happens in server components via auth()
// running in Node.js runtime. The middleware is NOT the security gate — server
// components are. This matches the Auth.js v5 recommended pattern for
// database-session adapters.
export function middleware(req: NextRequest) {
  const isDashboard = req.nextUrl.pathname.startsWith("/dashboard");
  if (!isDashboard) return NextResponse.next();

  // Auth.js v5 sets __Secure-authjs.session-token in HTTPS contexts (AFD).
  // Fallback to the non-Secure prefix for local dev (HTTP).
  const hasSession =
    req.cookies.has("__Secure-authjs.session-token") ||
    req.cookies.has("authjs.session-token");

  if (!hasSession) {
    const signinUrl = new URL("/auth/signin", req.url);
    return NextResponse.redirect(signinUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Match all routes except API, Next.js internals, and static assets.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
