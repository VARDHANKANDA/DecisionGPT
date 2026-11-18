"use client";

import { DATA_TABLES } from "@/lib/platform-api";

export function TablePicker({ value, onChange, label = "Data to look at" }: { value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <label className="block text-sm font-medium text-foreground">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 block min-h-[44px] w-full max-w-xs rounded-lg border border-border bg-surface px-3 text-base">
        {DATA_TABLES.map((t) => (
          <option key={t.key} value={t.key}>
            {t.label}
          </option>
        ))}
      </select>
    </label>
  );
}
