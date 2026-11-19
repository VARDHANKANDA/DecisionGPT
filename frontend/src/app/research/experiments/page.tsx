"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * The Reproducibility section has been removed from the Research Console.
 * Historical experiment records, manifests, and backend evaluation data remain preserved.
 * Old bookmarks are forwarded to the Research Overview.
 */
export default function ExperimentsMoved() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/research");
  }, [router]);
  return (
    <p className="text-sm text-muted">
      This section is not part of the current Research Console. Redirecting to the overview…
    </p>
  );
}
