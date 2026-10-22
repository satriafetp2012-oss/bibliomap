import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PendingPage, RecordView } from "../types";
import { DedupPanel } from "./DedupPanel";

function view(id: number, over: Partial<RecordView> = {}): RecordView {
  return {
    id,
    import_label: id === 1 ? "Web of Science" : "Scopus",
    source_format: id === 1 ? "wos" : "scopus",
    title: "Road traffic injury among motorcycle riders in Indonesia",
    authors: ["Santoso, B", "Lee, ML"],
    author_count: 2,
    year: 2021,
    source_title: "Injury Prevention",
    document_type: "article",
    doi: id === 1 ? "10.5555/a" : null,
    volume: "27",
    issue: "3",
    pages: "245-252",
    abstract: "Motorcycle crashes are a leading cause of injury.",
    ...over,
  };
}

const page: PendingPage = {
  total: 2,
  items: [
    {
      a: view(1),
      b: view(2, { title: "Road traffic injury among motorbike riders in Indonesia" }),
      title_similarity: 96,
      reasons: ["title:96", "year_equal", "first_author_equal"],
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

function mockFetch(pages: PendingPage[]) {
  let call = 0;
  return vi.spyOn(globalThis, "fetch").mockImplementation((url, init) => {
    if (String(url).includes("/dedup/pending")) {
      const body = pages[Math.min(call++, pages.length - 1)];
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    }
    expect(init?.method).toBe("POST");
    return Promise.resolve(new Response(null, { status: 204 }));
  });
}

describe("DedupPanel", () => {
  it("shows both records side by side and marks differing fields", async () => {
    mockFetch([page]);
    render(<DedupPanel workspaceId="ws1" autoRemoved={4} active onChanged={() => {}} />);

    expect(
      await screen.findByText("4 duplikat sudah digabung otomatis (DOI sama, atau judul, tahun, dan penulis pertama identik)."),
    ).toBeInTheDocument();
    expect(screen.getByText("2 pasangan menunggu keputusan Anda.")).toBeInTheDocument();
    expect(
      screen.getByText(/Kemiripan judul 96% · Tahun sama · Penulis pertama sama/),
    ).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Web of Science" })).toBeInTheDocument();
    // DOI differs between the two records, so both cells are highlighted.
    const doiRow = screen.getByRole("row", { name: /DOI/ });
    expect(doiRow.querySelectorAll("td.diff")).toHaveLength(2);
  });

  it("sends a merge decision and reloads", async () => {
    const empty: PendingPage = { total: 0, items: [] };
    const fetchMock = mockFetch([page, empty]);
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<DedupPanel workspaceId="ws1" autoRemoved={0} active onChanged={onChanged} />);

    await user.click(await screen.findByRole("button", { name: "Duplikat, gabungkan" }));

    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    const decision = fetchMock.mock.calls.find(([u]) => String(u).includes("/decisions"));
    expect(JSON.parse(decision![1]!.body as string)).toEqual({
      record_a: 1,
      record_b: 2,
      same: true,
    });
    expect(await screen.findByText("Tidak ada pasangan yang perlu ditinjau.")).toBeInTheDocument();
  });

  it("supports the N keyboard shortcut only while active", async () => {
    const fetchMock = mockFetch([page]);
    const user = userEvent.setup();
    const { rerender } = render(
      <DedupPanel workspaceId="ws1" autoRemoved={0} active={false} onChanged={() => {}} />,
    );
    await screen.findByRole("button", { name: "Bukan duplikat" });
    await user.keyboard("n");
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/decisions"))).toBe(false);

    rerender(<DedupPanel workspaceId="ws1" autoRemoved={0} active onChanged={() => {}} />);
    await user.keyboard("n");

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/decisions"));
      expect(JSON.parse(call![1]!.body as string).same).toBe(false);
    });
  });
});
