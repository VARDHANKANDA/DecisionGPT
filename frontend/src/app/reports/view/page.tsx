"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { platform } from "@/lib/platform-api";
import { Notice, Spinner, btnSecondary } from "@/components/simple";
import { LoadView, useLoad } from "@/components/agent-ui";
import { ReportView, Workspace } from "@/components/platform-ui";

function Body() {
  const rid = useSearchParams().get("id");
  const load = useLoad((b) => (rid ? platform.report(b, rid) : Promise.reject(new Error("Missing report id"))));
  if (!rid) return <Notice tone="warning">No report was chosen. Open one from the Reports list.</Notice>;
  return (
    <LoadView load={load} label="Opening the report…">
      {(r) => (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-3 print:hidden">
            <Link href="/reports" className={btnSecondary}>
              All reports
            </Link>
            <button className={btnSecondary} onClick={() => window.print()}>
              Print or save as PDF
            </button>
          </div>
          <p className="text-sm text-muted">This is the saved copy from {r.created_at.slice(0, 10)}. It does not change when your data does.</p>
          <ReportView payload={r.payload} />
        </div>
      )}
    </LoadView>
  );
}

export default function ReportViewPage() {
  return (
    <Workspace title="Report" wide>
      {() => (
        <Suspense fallback={<Spinner label="Opening the report…" />}>
          <Body />
        </Suspense>
      )}
    </Workspace>
  );
}
