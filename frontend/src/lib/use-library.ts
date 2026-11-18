"use client";

import { useEffect, useState } from "react";
import { api, type DataLibraryEntry } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";

/** The person's data library (what they have added), loaded once per business. */
export function useLibrary() {
  const { business } = useBusiness();
  const [state, setState] = useState<{ id: string; library: DataLibraryEntry[] } | null>(null);

  useEffect(() => {
    if (!business) return;
    let cancelled = false;
    api
      .getDataLibrary(business.id)
      .then((library) => !cancelled && setState({ id: business.id, library }))
      .catch(() => !cancelled && setState({ id: business.id, library: [] }));
    return () => {
      cancelled = true;
    };
  }, [business]);

  return state && business && state.id === business.id ? state.library : null;
}
