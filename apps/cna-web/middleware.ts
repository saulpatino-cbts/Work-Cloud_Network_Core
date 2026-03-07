import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// NextAuth v5 middleware — protect all routes under /dashboard/*
// and redirect unauthenticated users to /auth/signin.
export default auth(function middleware(req: NextRequest) {
  // auth() returns the session attached to req.auth
  const session = (req as NextRequest & { auth?: unknown }).auth;

  const isDashboard = req.nextUrl.pathname.startsWith("/dashboard");
  if (isDashboard && !session) {
    const signinUrl = new URL("/auth/signin", req.url);
    return NextResponse.redirect(signinUrl);
  }

  return NextResponse.next();
});

export const config = {
  // Match all routes except static files and API routes.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
