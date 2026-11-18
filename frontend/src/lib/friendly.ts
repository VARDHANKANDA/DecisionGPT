import { ApiError } from "@/lib/api";

export interface FriendlyError {
  /** What the person sees. Plain language, never a status code. */
  message: string;
  /** Kept for the collapsible "Technical details" section only. */
  technical: string;
}

const SAFE_DEFAULT = "We couldn't do that right now. Your data is safe — please try again.";

/**
 * Turn any thrown value into something a non-technical person can read.
 * Server messages for expected problems (validation, "not enough data") are already
 * written in plain language by the backend, so those are shown as-is; anything that
 * looks like a crash or a network failure gets a calm generic message instead.
 */
export function friendlyError(err: unknown, fallback = SAFE_DEFAULT): FriendlyError {
  if (err instanceof ApiError) {
    const technical = `${err.status} ${err.code}: ${err.message}`;
    if (err.status === 401) return { message: "Your sign-in has expired. Please sign in again.", technical };
    if (err.status === 403) return { message: "You don't have access to this.", technical };
    if (err.status === 404) return { message: "We couldn't find that. It may have been removed.", technical };
    if (err.status >= 400 && err.status < 500 && err.message) return { message: err.message, technical };
    return { message: fallback, technical };
  }
  if (err instanceof TypeError) {
    return {
      message: "We couldn't reach DecisionGPT. Please check your internet connection and try again.",
      technical: String(err.message),
    };
  }
  return { message: fallback, technical: err instanceof Error ? err.message : String(err) };
}

/** "Today", "Yesterday", "3 days ago", or a short date. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Plain-language names for every field a person might see mentioned in a data problem. */
export const FIELD_LABELS: Record<string, string> = {
  external_product_id: "Product ID",
  external_customer_id: "Customer ID",
  name: "Product name",
  category: "Category",
  unit_cost: "Cost each",
  selling_price: "Selling price",
  stock_quantity: "In stock",
  segment: "Customer group",
  first_purchase_date: "First purchase date",
  last_purchase_date: "Last purchase date",
  purchase_frequency: "Times bought",
  monetary_value: "Total spent",
  sale_date: "Date",
  quantity: "Quantity",
  unit_price: "Price each",
  discount: "Discount",
  revenue: "Total amount",
  campaign_date: "Date",
  channel: "Where it ran",
  campaign_name: "Campaign name",
  spend: "Amount spent",
  impressions: "Times shown",
  clicks: "Clicks",
  conversions: "Orders",
  attributed_revenue: "Sales from it",
  date: "Date",
  stock_level: "Stock level",
  reorder_level: "Reorder level",
  period_date: "Month",
};

export function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field.replace(/_/g, " ");
}

/** Rewrite a server-side data-quality message in everyday words. */
export function explainIssue(issue: string): string {
  let m = issue.match(/Required field '(\w+)' is missing after mapping/);
  if (m) return `We couldn't find a column for “${fieldLabel(m[1])}”.`;
  m = issue.match(/(\d+) duplicate rows detected/);
  if (m) return `${m[1]} row${m[1] === "1" ? " appears" : "s appear"} more than once.`;
  m = issue.match(/(\d+) rows have an unparseable date in '(\w+)'/);
  if (m) return `${m[1]} row${m[1] === "1" ? " has" : "s have"} a date we couldn't read (in “${fieldLabel(m[2])}”).`;
  if (/No rows found/i.test(issue)) return "The file doesn't seem to have any rows of data.";
  return issue;
}

/** Plain-language message for a "too many attempts" (HTTP 429) answer, using the server's retry information. Never blames the person's password. */
export function tooManyAttempts(err: ApiError): string {
  const raw = Number((err.details as { retry_after_seconds?: unknown } | undefined)?.retry_after_seconds);
  if (!Number.isFinite(raw) || raw <= 0) return "Too many attempts. Please wait a few minutes and try again.";
  const minutes = Math.ceil(raw / 60);
  return minutes <= 1
    ? "Too many attempts. Please wait a minute and try again."
    : `Too many attempts. Please wait about ${minutes} minutes and try again.`;
}
