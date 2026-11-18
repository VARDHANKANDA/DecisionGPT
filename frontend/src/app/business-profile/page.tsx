"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { isDemoBusiness } from "@/lib/demo";
import { DATA_GROUP_NAME } from "@/lib/features";
import { friendlyError, type FriendlyError } from "@/lib/friendly";
import { ErrorBox, Notice, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";

export default function BusinessProfilePage() {
  const { business, loading, refresh } = useBusiness();
  const [name, setName] = useState<string | null>(null);
  const [description, setDescription] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<FriendlyError | null>(null);
  const library = useLoad((id) => api.getDataLibrary(id));

  if (loading) return <Page title="Business Profile"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Business Profile" subtitle="Set up your business first.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business</Link>
      </Page>
    );
  }

  const demo = isDemoBusiness(business);
  const nameValue = name ?? business.name;
  const descValue = description ?? business.description ?? "";

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!business) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.updateBusiness(business.id, { name: nameValue.trim(), description: descValue.trim() || null });
      await refresh();
      setName(null);
      setDescription(null);
      setSaved(true);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Page title="Business Profile" subtitle="What DecisionGPT knows about your business, and what data is available for analysis." wide>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-border bg-surface p-6">
          <h2 className="text-xl font-semibold text-foreground">About your business</h2>
          {demo ? <div className="mt-3"><Notice tone="warning" title="Demo business">This is sample data for demonstration, not a real business.</Notice></div> : null}
          <dl className="mt-4 grid grid-cols-2 gap-3 text-base">
            <div><dt className="text-sm text-muted">Industry</dt><dd className="font-medium text-foreground">{business.industry}</dd></div>
            <div><dt className="text-sm text-muted">Type</dt><dd className="font-medium text-foreground">{business.business_type}</dd></div>
            <div><dt className="text-sm text-muted">Size</dt><dd className="font-medium text-foreground">{business.business_size}</dd></div>
            <div><dt className="text-sm text-muted">Country · Currency</dt><dd className="font-medium text-foreground">{business.country} · {business.currency}</dd></div>
          </dl>
          <form onSubmit={save} className="mt-5 border-t border-border pt-5">
            <label className="block">
              <span className="text-base font-medium text-foreground">Business name</span>
              <input className="input mt-1 min-h-[48px] text-base" value={nameValue} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label className="mt-4 block">
              <span className="text-base font-medium text-foreground">About your business (optional)</span>
              <textarea className="input mt-1 min-h-[96px] text-base" value={descValue} onChange={(e) => setDescription(e.target.value)} />
            </label>
            {error ? <div className="mt-4"><ErrorBox error={error} /></div> : null}
            {saved ? <p role="status" className="mt-4 text-base text-success">✓ Saved</p> : null}
            <div className="mt-4"><button type="submit" className={btnPrimary} disabled={saving || !nameValue.trim()}>{saving ? "Saving…" : "Save changes"}</button></div>
            <p className="mt-3 text-xs text-muted">Only the name and description can be edited here.</p>
          </form>
        </section>

        <div className="space-y-6">
          <Panel title="Data available for analysis" note="Each kind of data below is used automatically by the analyses that need it.">
            <LoadView load={library} label="Checking your data…">
              {(lib) => (
                <ul className="divide-y divide-border rounded-xl border border-border">
                  {lib.map((d) => (
                    <li key={d.type} className="flex items-center justify-between gap-3 px-4 py-3 text-base">
                      <span className="text-foreground">{DATA_GROUP_NAME[d.type]}</span>
                      <span className={d.rows > 0 ? "text-foreground" : "text-warning"}>{d.rows > 0 ? `${d.rows.toLocaleString("en-IN")} rows` : "Not added yet"}</span>
                    </li>
                  ))}
                </ul>
              )}
            </LoadView>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link href="/data" className={btnSecondary}>Upload &amp; manage data</Link>
              <Link href="/data/quality" className={btnSecondary}>Data quality</Link>
            </div>
          </Panel>
        </div>
      </div>
    </Page>
  );
}
