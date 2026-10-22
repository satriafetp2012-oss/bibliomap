import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Statistics } from "../types";
import { StatsPanel } from "./StatsPanel";

function entity(label: string, documents: number, h: number) {
  return {
    key: label.toLowerCase(),
    label,
    documents,
    citations: documents * 10,
    h_index: h,
    g_index: h + 1,
    m_index: 0.5,
    first_year: 2018,
  };
}

const stats: Statistics = {
  overview: {
    documents: 720,
    sources: 148,
    authors: 3120,
    single_authored: 24,
    keywords_author: 900,
    keywords_index: 1200,
    references: 11953,
    year_min: 2005,
    year_max: 2024,
    mean_citations: 31.4,
    total_citations: 22608,
    mean_authors_per_document: 6.8,
    collaboration_index: 7.1,
    international_coauthorship_pct: 38.2,
    annual_growth_rate_pct: 12.5,
    documents_per_year: [
      { year: 2022, count: 40, mean_citations: 5.2 },
      { year: 2023, count: 60, mean_citations: 2.1 },
      { year: 2024, count: 80, mean_citations: null },
    ],
    document_types: { article: 600, review: 120 },
  },
  top_sources: [entity("Circulation", 42, 20)],
  top_authors: [entity("Mehran, Roxana", 30, 18)],
  top_affiliations: [entity("Univ Gadjah Mada", 12, 6)],
  top_countries: [entity("Indonesia", 25, 9)],
  top_keywords: [entity("stent", 90, 30)],
  lotka: {
    rows: [
      { documents_written: 1, authors: 2400, proportion: 0.77, fitted_proportion: 0.74 },
      { documents_written: 2, authors: 500, proportion: 0.16, fitted_proportion: 0.18 },
    ],
    exponent: 2.14,
    constant: 0.74,
    r_squared: 0.981,
    ks_statistic: 0.031,
  },
  bradford: {
    rows: [{ rank: 1, key: "circ", label: "Circulation", documents: 42, cumulative: 42, zone: 1 }],
    zone_sources: [6, 28, 114],
    zone_documents: [240, 241, 239],
    multiplier: 4.4,
  },
};

afterEach(() => vi.restoreAllMocks());

describe("StatsPanel", () => {
  it("renders the overview, chart and laws in Indonesian", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(stats), { status: 200 }),
    );

    render(<StatsPanel workspaceId="ws1" version={1} />);

    expect(await screen.findByText("Statistik deskriptif")).toBeInTheDocument();
    expect(screen.getByText("2005–2024")).toBeInTheDocument();
    expect(screen.getByText("12.5%")).toBeInTheDocument();
    expect(screen.getByText("31.4")).toBeInTheDocument();
    // The chart draws one bar per year, each with its own tooltip.
    const chart = screen.getByRole("img", { name: "Produksi ilmiah tahunan" });
    expect(chart.querySelectorAll("rect")).toHaveLength(3);
    expect(chart.textContent).toContain("2024: 80");
    // Lotka exponent near 2 is the classic result.
    expect(screen.getByText("2.14")).toBeInTheDocument();
    expect(screen.getByText("6 sumber · 240 dokumen")).toBeInTheDocument();
  });

  it("switches between rankings", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(stats), { status: 200 }),
    );
    const user = userEvent.setup();
    render(<StatsPanel workspaceId="ws1" version={1} />);

    // Sources are shown first (Circulation also appears in the Bradford table).
    expect(await screen.findAllByRole("cell", { name: "Circulation" })).not.toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Penulis" }));
    expect(screen.getByRole("cell", { name: "Mehran, Roxana" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Negara" }));
    expect(screen.getByRole("cell", { name: "Indonesia" })).toBeInTheDocument();
  });

  it("shows an empty state when nothing passed the filters", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ ...stats, overview: { ...stats.overview, documents: 0 } }),
        { status: 200 },
      ),
    );

    render(<StatsPanel workspaceId="ws1" version={1} />);

    expect(
      await screen.findByText("Belum ada data. Impor dulu di tab Impor."),
    ).toBeInTheDocument();
  });
});
