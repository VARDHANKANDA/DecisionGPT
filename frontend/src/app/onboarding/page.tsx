"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { Card, PageHeader, PrimaryButton } from "@/components/ui";

const INDUSTRIES = ["Apparel / D2C", "Retail", "E-commerce", "F&B", "Other"];
const BUSINESS_TYPES = ["D2C", "Retail", "Marketplace seller", "Wholesale"];
const BUSINESS_SIZES = ["Solo / 1-5 employees", "Small (6-25)", "Medium (26-100)"];

export default function OnboardingPage() {
  const router = useRouter();
  const { setBusinessId } = useBusiness();

  const [name, setName] = useState("");
  const [industry, setIndustry] = useState(INDUSTRIES[0]);
  const [businessType, setBusinessType] = useState(BUSINESS_TYPES[0]);
  const [businessSize, setBusinessSize] = useState(BUSINESS_SIZES[0]);
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const business = await api.createBusiness({
        name,
        industry,
        business_type: businessType,
        business_size: businessSize,
        description: description || undefined,
      });
      setBusinessId(business.id);
      router.push("/data/upload");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl px-6 py-16">
      <PageHeader
        title="Tell us about your business"
        subtitle="A few basics — you'll upload your actual data next."
      />

      <Card>
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <Field label="Business name">
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Saanjh Clothing Co."
              className="input"
            />
          </Field>

          <Field label="Industry">
            <select value={industry} onChange={(e) => setIndustry(e.target.value)} className="input">
              {INDUSTRIES.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>

          <Field label="Business type">
            <select value={businessType} onChange={(e) => setBusinessType(e.target.value)} className="input">
              {BUSINESS_TYPES.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>

          <Field label="Business size">
            <select value={businessSize} onChange={(e) => setBusinessSize(e.target.value)} className="input">
              {BUSINESS_SIZES.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>

          <Field label="Description (optional)">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="input resize-none"
            />
          </Field>

          {error ? <p className="text-sm text-danger">{error}</p> : null}

          <PrimaryButton type="submit" disabled={submitting || !name}>
            {submitting ? "Creating..." : "Continue"}
          </PrimaryButton>
        </form>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {children}
    </label>
  );
}
