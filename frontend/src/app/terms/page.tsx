import Link from "next/link";

export default function TermsPage() {
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
            <span className="text-xs font-semibold uppercase tracking-wider text-blue-700">Legal Agreement</span>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Terms of Service</h1>
            <p className="mt-2 text-sm text-slate-500">Effective Date: October 2026 • Enterprise Customer Agreement</p>
          </div>

          <div className="mt-8 space-y-8 text-sm leading-relaxed text-slate-600">
            <section>
              <h2 className="text-lg font-bold text-slate-900">1. Acceptance of Terms</h2>
              <p className="mt-2">
                By creating an account, accessing, or utilizing the DecisionGPT platform, you agree to comply with and be bound
                by these Enterprise Terms of Service. If you are entering into this agreement on behalf of a corporate entity, you
                represent that you possess the authority to bind that entity.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">2. Advisory Nature of Decision Support</h2>
              <p className="mt-2">
                DecisionGPT provides computational decision intelligence, scenario simulations, and analytics based upon customer-supplied
                business datasets. All generated forecasts, scenarios, and multi-agent scores are informational decision-support aids designed
                to assist human leadership. Final strategic, financial, and operational decisions remain solely under human management discretion.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">3. User Responsibilities &amp; Data Accuracy</h2>
              <p className="mt-2">
                You are responsible for the validity, completeness, and lawful acquisition of any operational datasets ingested into the platform.
                The accuracy of deterministic metrics and predictive models depends directly upon the quality of the source data provided.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">4. Intellectual Property &amp; Customer Records</h2>
              <p className="mt-2">
                You retain all rights, title, and ownership of your ingested business data and derived reports. DecisionGPT retains all proprietary
                rights in the underlying software, machine learning architectures, agent coordination frameworks, and user interfaces.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-slate-900">5. Service Availability &amp; Support</h2>
              <p className="mt-2">
                DecisionGPT is maintained to enterprise uptime standards. Scheduled maintenance is communicated in advance. For enterprise
                support inquiries or service level agreement questions, please contact{" "}
                <a href="mailto:support@decisiongpt.ai" className="font-semibold text-blue-600 hover:underline">
                  support@decisiongpt.ai
                </a>.
              </p>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
