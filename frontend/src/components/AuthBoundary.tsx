"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { isPublicPath } from "@/lib/session";

/**
 * Client-side route guard. The backend is always the real security boundary
 * (every protected API call still needs a valid bearer token); this only keeps
 * the UI honest:
 *   - a signed-out visitor on a protected route is sent to /login
 *   - a signed-in visitor on /login is sent to their workspace (by role)
 *   - protected content is never rendered before the session check resolves,
 *     so refresh / back-navigation after logout never flash stale data.
 */
export function AuthBoundary({ children }: { children: React.ReactNode }) {
  const { user, isAdmin, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isPublic = isPublicPath(pathname);
  const isResearch = pathname.startsWith("/research");
  // The research area has its own auth handling (session admin OR console token).
  const needsAuth = !isPublic && !isResearch;

  useEffect(() => {
    if (loading) return;
    if (needsAuth && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    } else if (pathname === "/login" && user) {
      router.replace(isAdmin ? "/research" : "/dashboard");
    }
  }, [loading, user, isAdmin, needsAuth, pathname, router]);

  if (loading && !isPublic) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-live="polite">
        <span className="text-sm text-muted">Loading your workspace…</span>
      </div>
    );
  }

  // Hold protected content back until the redirect above has a chance to run.
  if (needsAuth && !user) return null;
  if (pathname === "/login" && user) return null;

  return <>{children}</>;
}
