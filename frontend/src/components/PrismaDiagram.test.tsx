import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PrismaFlow } from "../types";
import { PrismaDiagram } from "./PrismaDiagram";

const flow: PrismaFlow = {
  identified: 1200,
  identified_by_source: [
    { label: "Scopus", count: 700 },
    { label: "PubMed", count: 500 },
  ],
  duplicates_removed: 320,
  automation_ineligible: 80,
  automation_ineligible_by_reason: { year: 50, document_type: 30 },
  other_removed: 0,
  screened: 800,
  screening_excluded: null,
  sought_for_retrieval: null,
  not_retrieved: null,
  assessed_for_eligibility: null,
  reports_excluded: null,
  included: null,
  pending_duplicate_reviews: 3,
};

afterEach(() => vi.restoreAllMocks());

describe("PrismaDiagram", () => {
  it("renders PRISMA counts in Indonesian with unknown stages blank", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(flow), { status: 200 }),
    );

    render(<PrismaDiagram workspaceId="ws1" version={1} />);

    expect(
      await screen.findByText("Rekaman teridentifikasi dari basis data (n = 1200)"),
    ).toBeInTheDocument();
    expect(screen.getByText("• Scopus: 700")).toBeInTheDocument();
    expect(screen.getByText("Duplikat dihapus (n = 320)")).toBeInTheDocument();
    expect(screen.getByText("• Tahun: 50")).toBeInTheDocument();
    expect(screen.getByText("Rekaman disaring (n = 800)")).toBeInTheDocument();
    // Stages filled in a later phase show a placeholder, not zero.
    expect(screen.getByText("Studi termasuk dalam tinjauan (n = …)")).toBeInTheDocument();
    expect(
      screen.getByText("Masih ada 3 pasangan duplikat yang belum ditinjau; angka dapat berubah."),
    ).toBeInTheDocument();
  });
});
