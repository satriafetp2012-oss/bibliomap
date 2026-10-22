import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OpenAlexPanel } from "./OpenAlexPanel";

const record = {
  source_format: "openalex",
  source_id: "W1",
  title: "Smart helmet prototype",
  authors: [{ name: "Ana", full_name: "Ana", orcid: null, affiliations: [] }],
  year: 2018,
  source_title: "J Phys Conf Ser",
  document_type: "conference_paper",
  doi: null,
  cited_by: 4,
};

afterEach(() => vi.restoreAllMocks());

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("OpenAlexPanel", () => {
  it("builds the query, counts, then imports", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        json({ count: 650, query_url: "https://api.openalex.org/works?filter=x" }),
      )
      .mockResolvedValueOnce(
        json({
          record_count: 1,
          total_available: 650,
          truncated: true,
          cost_usd: 0.001,
          query_url: "https://api.openalex.org/works?filter=x",
          result: { source_format: "openalex", records: [record], warnings: [] },
        }),
      );
    const user = userEvent.setup();
    render(<OpenAlexPanel />);

    await user.type(screen.getByLabelText(/Kata kunci/), "helmet AND indonesia");
    await user.type(screen.getByLabelText("Tahun dari"), "2015");
    await user.type(screen.getByLabelText("Tahun sampai"), "2024");
    await user.click(screen.getByLabelText("Review"));
    await user.type(screen.getByLabelText(/^Bahasa/), "EN, id");
    // Select the default value so typing replaces it.
    await user.tripleClick(screen.getByLabelText("Batas rekaman"));
    await user.keyboard("500");
    await user.click(screen.getByRole("button", { name: "Hitung hasil" }));

    expect(await screen.findByText("650 karya cocok dengan query ini.")).toBeInTheDocument();
    expect(
      screen.getByText("Akan diimpor 500 rekaman (perkiraan biaya OpenAlex $0.003)."),
    ).toBeInTheDocument();

    const sent = JSON.parse(fetchMock.mock.calls[0][1]!.body as string);
    expect(sent).toEqual({
      query: {
        terms: "helmet AND indonesia",
        scope: "title_and_abstract",
        year_from: 2015,
        year_to: 2024,
        types: ["review"],
        languages: ["en", "id"],
        open_access_only: false,
        max_results: 500,
      },
      api_key: null,
    });

    await user.click(screen.getByRole("button", { name: "Impor 500 rekaman" }));

    expect(
      await screen.findByText("1 rekaman diimpor dari OpenAlex (total tersedia 650)."),
    ).toBeInTheDocument();
    expect(screen.getByText("Smart helmet prototype")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Makalah konferensi" })).toBeInTheDocument();
    expect(fetchMock.mock.calls[1][0]).toBe("/api/openalex/import");
  });

  it("shows validation and budget errors from the server", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      json({ detail: "Kuota harian OpenAlex habis." }, 429),
    );
    const user = userEvent.setup();
    render(<OpenAlexPanel />);

    await user.type(screen.getByLabelText(/Kata kunci/), "helmet");
    await user.type(screen.getByLabelText(/API key OpenAlex/), "my-key");
    await user.click(screen.getByRole("button", { name: "Hitung hasil" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Kuota harian OpenAlex habis.");
  });
});
