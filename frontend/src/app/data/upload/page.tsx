"use client";

import { ActionCard, Page } from "@/components/simple";

export default function AddDataPage() {
  return (
    <Page title="Add your business data" subtitle="You can upload a file, enter data yourself, or start with an example.">
      <div className="grid gap-4 sm:grid-cols-3">
        <ActionCard
          href="/data/upload/file"
          icon="📁"
          title="Upload a file"
          description="Upload CSV or Excel"
        />
        <ActionCard
          href="/data/manual"
          icon="✏️"
          title="Enter data manually"
          description="Create a table and enter your information"
        />
        <ActionCard
          href="/data/samples"
          icon="📋"
          title="Use sample data"
          description="See an example before adding your own data"
        />
      </div>
      <p className="mt-8 text-base text-muted">
        New data is added to what you already have, and uses the fields DecisionGPT supports. You can look at, change or
        remove it any time from My Data.
      </p>
    </Page>
  );
}
