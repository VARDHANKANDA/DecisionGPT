import { describe, expect, it } from "vitest";
import { SAMPLES } from "@/lib/sample-data";

const sample = (id: string) => SAMPLES.find((s) => s.id === id)!;

describe("sample data is internally consistent and clearly an example", () => {
  it("every sale total is quantity × price", () => {
    for (const r of sample("sales").rows()) {
      expect(r.revenue).toBe(Number(r.quantity) * Number(r.unit_price));
    }
  });

  it("sales refer only to example products and customers that exist in their companion samples", () => {
    const products = new Set(sample("products").rows().map((r) => r.external_product_id));
    const customers = new Set(sample("customers").rows().map((r) => r.external_customer_id));
    for (const r of sample("sales").rows()) {
      expect(products.has(r.product)).toBe(true);
      expect(customers.has(r.customer)).toBe(true);
    }
  });

  it("each customer's total spent equals the sum of their example sales", () => {
    const sales = sample("sales").rows();
    for (const c of sample("customers").rows()) {
      const mine = sales.filter((s) => s.customer === c.external_customer_id);
      expect(c.monetary_value).toBe(mine.reduce((sum, s) => sum + Number(s.revenue), 0));
      expect(c.purchase_frequency).toBe(mine.length);
    }
  });

  it("profit = income − cost of goods − running costs", () => {
    for (const r of sample("finance").rows()) {
      expect(r.net_profit).toBe(Number(r.revenue) - Number(r.cogs) - Number(r.operating_expenses));
    }
  });

  it("example IDs and names are marked so they can't be mistaken for real data", () => {
    for (const p of sample("products").rows()) {
      expect(String(p.external_product_id)).toMatch(/^EX-/);
      expect(String(p.name)).toMatch(/^Example:/);
    }
  });

  it("every sample explains each of its columns in plain language", () => {
    for (const s of SAMPLES) {
      for (const c of s.columns) expect(c.meaning.length).toBeGreaterThan(8);
    }
  });
});
