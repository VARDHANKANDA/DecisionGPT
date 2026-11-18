import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { IngestionJob } from "@/lib/api";

const uploadData = vi.fn();
const confirmMapping = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      uploadData: (...a: unknown[]) => uploadData(...a),
      confirmMapping: (...a: unknown[]) => confirmMapping(...a),
      getTable: () => Promise.resolve({ title: "Sales", total: 3, columns: [], rows: [] }),
    },
  };
});
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Shop" }, loading: false }) }));
vi.mock("@/lib/use-library", () => ({ useLibrary: () => [] }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { ApiError } from "@/lib/api";
import UploadFilePage from "./page";

function job(over: Partial<IngestionJob> & { summary_json?: IngestionJob["summary_json"] }): IngestionJob {
  return {
    id: "j1",
    business_id: "b1",
    filename: "sales.csv",
    status: "completed",
    detected_types_json: ["sales"],
    mapping_json: {},
    summary_json: {},
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const completed = job({
  summary_json: {
    rows_ingested: { sales: 8 },
    original_kept: true,
    datasets: [
      {
        type: "sales",
        source: "sales",
        rows_read: 10,
        rows_after_cleaning: 10,
        rows_imported: 8,
        rows_skipped: 2,
        skipped_reasons: { "Date could not be read": 2 },
        skipped_examples: [{ row: 4, reason: "Date could not be read (not-a-date)" }],
        columns_in_file: ["Date", "Qty", "Notes"],
        columns_used: [{ column: "Date", as: "date" }],
        columns_not_used: ["Notes"],
        columns_removed_empty: [],
        renamed_columns: [],
        duplicate_rows: 1,
        actions: [{ code: "trim", message: "Extra spaces were removed from text values.", count: 12 }],
        warnings: ["1 row looks like a repeat of another row. It was kept."],
        encoding: "cp1252",
        delimiter: ";",
      },
    ],
  },
});

async function pick(name = "sales.csv", body = "Date,Qty\n2026-01-01,2\n") {
  const input = screen.getByLabelText("Choose a CSV or Excel file") as HTMLInputElement;
  const file = new File([body], name, { type: "text/csv" });
  fireEvent.change(input, { target: { files: [file] } });
  await screen.findByText(name);
  return file;
}

beforeEach(() => {
  uploadData.mockReset();
  confirmMapping.mockReset();
});

describe("Upload page: result report", () => {
  it("shows what was imported, what was left out and why, what was tidied, and that unused columns are kept", async () => {
    uploadData.mockResolvedValue(completed);
    render(<UploadFilePage />);
    await pick();
    fireEvent.click(screen.getByRole("button", { name: "Add this data to My Data" }));
    expect(await screen.findByText("What we did with your file")).toBeTruthy();
    const report = screen.getByRole("region", { name: /Import report/ });
    expect(report.textContent).toContain("Rows found in the file10");
    expect(report.textContent).toContain("Rows added to My Data8");
    expect(report.textContent).toMatch(/Rows left out\D*2/);
    expect(report.textContent).toContain("Date could not be read: 2 rows");
    expect(report.textContent).toContain("Extra spaces were removed from text values. (12)");
    expect(report.textContent).toContain("1 row looks like a repeat of another row. It was kept.");
    expect(report.textContent).toContain("Nothing was deleted");
    expect(report.textContent).toContain("We read this file as semicolon-separated text, encoding cp1252.");
    expect(screen.getByText("Notes")).toBeTruthy();
    expect(screen.getByText(/original file was kept unchanged/)).toBeTruthy();
  });
});

describe("Upload page: progress and double submit", () => {
  it("shows progress while sending and sends the file once however many times the button is clicked", async () => {
    let finish: (j: IngestionJob) => void = () => {};
    uploadData.mockImplementation((_b, _f, _t, opts: { onProgress: (n: number) => void }) => {
      opts.onProgress(0.5);
      return new Promise<IngestionJob>((r) => (finish = r));
    });
    render(<UploadFilePage />);
    await pick();
    const button = screen.getByRole("button", { name: "Add this data to My Data" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(await screen.findByText(/Sending your file… 50%/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Adding your data…" }) as HTMLButtonElement).disabled).toBe(true);
    expect(uploadData).toHaveBeenCalledTimes(1);
    finish(completed);
    expect(await screen.findByText("What we did with your file")).toBeTruthy();
  });
});

describe("Upload page: failure and retry", () => {
  it("keeps the chosen file after a network failure and lets the person try again", async () => {
    uploadData.mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(completed);
    render(<UploadFilePage />);
    await pick();
    fireEvent.click(screen.getByRole("button", { name: "Add this data to My Data" }));
    expect(await screen.findByText(/couldn't reach DecisionGPT/)).toBeTruthy();
    expect(screen.getByText("sales.csv")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("What we did with your file")).toBeTruthy();
    expect(uploadData).toHaveBeenCalledTimes(2);
  });

  it("shows the server's plain-language rejection as is", async () => {
    uploadData.mockRejectedValue(new ApiError(422, "VALIDATION_FAILED", "This file is larger than the 10 MB limit.", {}));
    render(<UploadFilePage />);
    await pick();
    fireEvent.click(screen.getByRole("button", { name: "Add this data to My Data" }));
    expect(await screen.findByText("This file is larger than the 10 MB limit.")).toBeTruthy();
  });

  it("explains a failed import, says nothing was saved, and offers a retry", async () => {
    uploadData.mockResolvedValue(
      job({ status: "failed", error_message: "most rows (9 of 10) could not be imported (Date could not be read: 9). Nothing was imported." }),
    );
    render(<UploadFilePage />);
    await pick();
    fireEvent.click(screen.getByRole("button", { name: "Add this data to My Data" }));
    expect(await screen.findByText(/Nothing was saved, and your existing data is unchanged/)).toBeTruthy();
    expect(screen.getByText(/most rows \(9 of 10\)/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try the same file again" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Import it again anyway" })).toBeNull();
  });
});

describe("Upload page: the same file twice", () => {
  it("only re-sends an already imported file when the person explicitly chooses to", async () => {
    uploadData
      .mockResolvedValueOnce(
        job({
          status: "failed",
          error_message: "This exact file was already imported on 05 Jan 2026. Nothing was added.",
          summary_json: { duplicate_of: { job_id: "j0", imported_on: "05 Jan 2026" } },
        }),
      )
      .mockResolvedValueOnce(completed);
    render(<UploadFilePage />);
    await pick();
    fireEvent.click(screen.getByRole("button", { name: "Add this data to My Data" }));
    expect(await screen.findByText("This file was already added")).toBeTruthy();
    expect(uploadData.mock.calls[0][3].allowDuplicateFile).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Import it again anyway" }));
    await screen.findByText("What we did with your file");
    expect(uploadData.mock.calls[1][3].allowDuplicateFile).toBe(true);
  });
});

describe("Upload page: unsupported files", () => {
  it("refuses old .xls files with a way forward and never sends them", async () => {
    render(<UploadFilePage />);
    await pick("old.xls", "x");
    expect(await screen.findByText(/Old Excel files \(\.xls\) can't be read safely/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Add this data to My Data" }) as HTMLButtonElement).disabled).toBe(true);
    expect(uploadData).not.toHaveBeenCalled();
  });

  it("refuses other file types", async () => {
    render(<UploadFilePage />);
    await pick("notes.pdf", "x");
    expect(await screen.findByText("We can't read this kind of file")).toBeTruthy();
    expect(uploadData).not.toHaveBeenCalled();
  });
});

describe("Upload page: questions instead of guesses", () => {
  const pending = job({
    status: "needs_mapping_confirmation",
    mapping_json: {
      sales: {
        sheet: "sales",
        type: "sales",
        suggested_mapping: { Day: "date" },
        unmapped_required_fields: ["quantity"],
        available_columns: ["Day", "Count"],
        date_questions: [{ field: "date", column: "Day", examples: ["03/04/2026", "05/06/2026"] }],
      },
    },
  });

  it("asks which column and which date order, and will not continue until both are answered", async () => {
    uploadData.mockResolvedValue(pending);
    confirmMapping.mockResolvedValue(completed);
    render(<UploadFilePage />);
    await pick();
    fireEvent.click(screen.getByRole("button", { name: "Add this data to My Data" }));
    await screen.findByText("We need your help with a few things");
    const next = screen.getByRole("button", { name: "Continue" }) as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    expect(screen.getByText(/03\/04\/2026, 05\/06\/2026/)).toBeTruthy();

    fireEvent.change(screen.getByRole("combobox", { name: /Which column is/ }), { target: { value: "Count" } });
    expect(next.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/Day first/));
    expect(next.disabled).toBe(false);
    fireEvent.click(next);

    await waitFor(() => expect(confirmMapping).toHaveBeenCalled());
    const [, jobId, mappings, orders] = confirmMapping.mock.calls[0];
    expect(jobId).toBe("j1");
    expect(mappings.sales).toEqual({ Day: "date", Count: "quantity" });
    expect(orders).toEqual({ sales: { date: "day_first" } });
    expect(await screen.findByText("What we did with your file")).toBeTruthy();
  });
});
