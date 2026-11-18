import Link from "next/link";

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 antialiased selection:bg-blue-100 selection:text-blue-900">
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/95 px-6 py-4 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-white font-bold text-sm shadow-xs">
              D
            </div>
            <span className="text-base font-bold tracking-tight text-slate-900">DecisionGPT</span>
          </Link>
          <div className="flex items-center gap-4 text-sm font-medium">
            <Link href="/" className="text-slate-600 hover:text-slate-900 transition">
              Back to Home
            </Link>
            <Link
              href="/login"
              className="rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs text-white hover:bg-slate-800 transition shadow-xs"
            >
              Sign In
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-12 sm:py-16">
        <div className="rounded-2xl border border-slate-200 bg-white p-8 sm:p-12 shadow-xs">
          <div className="border-b border-slate-200 pb-6">
            <span className="text-xs font-semibold uppercase tracking-wider text-blue-700">Governance &amp; Trust</span>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Privacy Policy</h1>
            <p className="mt-2 text-sm text-slate-500">Effective Date: October 2026 • Enterprise Data Policy</p>
          </div>

          <div className="mt-8 space-y-8 text-sm leading-relaxed text-slate-600">
            <section>
              <h2 className="text-lg font-bold text-slate-900">1. Strict Tenant Isolation by Business ID</h2>
              <p className="mt-2">
                DecisionGPT enforces cryptographic and database-level tenancy boundaries. All uploaded transactional records,
                product catalogs, customer profiles, and inventory states are strictly partitioned by an immutable{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800 font-mono">business_id</code>.
                No enterprise user or organization can ever view, query, or infer another business entity’s operational records.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">2. External AI Boundary &amp; Zero Training on Customer Data</h2>
              <p className="mt-2">
                DecisionGPT uses external AI models (OpenAI official API) solely for natural language query classification
                into a strict closed JSON schema. Your proprietary sales ledgers, customer identities, and financial tables are
                never transmitted to external AI providers and are never used to train public or proprietary models.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">3. Deterministic Analytics Engine</h2>
              <p className="mt-2">
                All performance metrics, forecasting equations, and score computations are performed inside deterministic
                server-side execution pipelines. Calculations are mathematically auditable and can be traced directly back to
                the exact rows in your data store.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">4. Encryption in Transit and at Rest</h2>
              <p className="mt-2">
                All communication between client browsers and DecisionGPT APIs is encrypted using TLS 1.3. Stored datasets,
                session tokens, and configuration profiles are encrypted at rest using industry-standard AES-256 protocols.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">5. Data Retention &amp; Right to Erasure</h2>
              <p className="mt-2">
                Enterprise administrators retain full sovereignty over their records. You may export or purge your business datasets
                at any time via the workspace settings. Upon account closure, all associated business records and cached model artifacts
                are permanently deleted.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">6. Contact Governance</h2>
              <p className="mt-2">
                For questions regarding enterprise data handling or compliance verification, contact our Data Protection Office at{" "}
                <a href="mailto:privacy@decisiongpt.ai" className="font-semibold text-blue-600 hover:underline">
                  privacy@decisiongpt.ai
                </a>.
              </p>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
