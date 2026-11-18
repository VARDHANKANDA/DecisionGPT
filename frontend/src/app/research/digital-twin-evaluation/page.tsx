"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * The Digital Twin Evaluation section is hidden from the Research Console for now (2026-10-14).
 * The backend module, its data and historical experiments are untouched and recoverable; this route only
 * forwards old bookmarks to the overview so nothing leads to a removed section.
 */
export default function DigitalTwinEvaluationMoved() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/research");
  }, [router]);
  return <p className="text-sm text-muted">This section is not part of the current Research Console. Redirecting to the overview…</p>;
}
