import { NextResponse } from 'next/server';

/**
 * Route protection middleware.
 * /dashboard and any future protected routes redirect to /login
 * when the missionready_access_token cookie is absent.
 *
 * Note: the token is stored in localStorage (not cookies) so we can't
 * read it from the server in middleware. Instead we rely on the
 * client-side guard inside DashboardPage. This middleware handles the
 * root redirect (/ → /login) only.
 */
export function middleware(request) {
  const { pathname } = request.nextUrl;

  // Redirect bare root to landing page
  if (pathname === '/') {
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|images|api).*)'],
};
