import { NextRequest, NextResponse } from "next/server";

/**
 * UX gate for the internal dashboard: redirect to login when no auth cookie is
 * present. This is deliberately a presence check only — the token's signature,
 * expiry, and email allowlist are enforced by the API on every request.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname === "/admin/login") {
    return NextResponse.next();
  }
  const token = request.cookies.get("alma_admin_token")?.value;
  if (!token) {
    const url = request.nextUrl.clone();
    url.pathname = "/admin/login";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*", "/admin"],
};
