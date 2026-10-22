import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ImportPreview } from "../types";
import { ImportPanel } from "./ImportPanel";

const preview: ImportPreview = {
  filename: "savedrecs.txt",
  record_count: 1,
  result: {
    source_format: "wos",
    warnings: [{ record_index: 2, message: "Rekaman tanpa judul (TI)." }],
    records: [
      {
        source_format: "wos",
        source_id: "WOS:1",
        title: "Road traffic injury in Indonesia",
        authors: ["A", "B", "C", "D"].map((name) => ({
          name,
          full_name: null,
          orcid: null,
          affiliations: [],
        })),
        year: 2021,
        source_title: "INJURY PREVENTION",
        document_type: "article",
        doi: "10.5555/ip-2020-0001",
        cited_by: 12,
      },
    ],
  },
};

afterEach(() => vi.restoreAllMocks());

async function upload() {
  const user = userEvent.setup();
  render(<ImportPanel />);
  const input = screen.getByLabelText("Pilih file");
  await user.upload(input, new File(["PT J"], "savedrecs.txt"));
  await user.click(screen.getByRole("button", { name: "Pratinjau" }));
}

describe("ImportPanel", () => {
  it("shows parsed records in Indonesian", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(preview), { status: 200 }),
    );

    await upload();

    expect(
      await screen.findByText("1 rekaman dari savedrecs.txt (format Web of Science)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Road traffic injury in Indonesia")).toBeInTheDocument();
    expect(screen.getByText("A; B; C dkk.")).toBeInTheDocument();
    expect(screen.getByText("Artikel")).toBeInTheDocument();
    expect(screen.getByText("Rekaman ke-3: Rekaman tanpa judul (TI).")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "10.5555/ip-2020-0001" })).toHaveAttribute(
      "href",
      "https://doi.org/10.5555/ip-2020-0001",
    );
  });

  it("shows the server error message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Format file tidak dikenali." }), { status: 422 }),
    );

    await upload();

    expect(await screen.findByRole("alert")).toHaveTextContent("Format file tidak dikenali.");
  });
});
