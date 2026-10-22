import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ImportInfo } from "../types";
import { ImportPanel } from "./ImportPanel";

const info: ImportInfo = {
  id: 1,
  label: "Web of Science",
  source_format: "wos",
  origin: "savedrecs.txt",
  record_count: 160,
  warnings: [{ record_index: 2, message: "Rekaman tanpa judul (TI)." }],
  created_at: "2026-10-22T00:00:00Z",
};

afterEach(() => vi.restoreAllMocks());

async function upload() {
  const user = userEvent.setup();
  const onImported = vi.fn();
  render(<ImportPanel workspaceId="ws1" onImported={onImported} />);
  const input = screen.getByLabelText("Pilih file");
  await user.upload(input, new File(["PT J"], "savedrecs.txt"));
  await user.click(screen.getByRole("button", { name: "Impor" }));
  return onImported;
}

describe("ImportPanel", () => {
  it("imports into the workspace and reports warnings in Indonesian", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(info), { status: 201 }));

    const onImported = await upload();

    expect(
      await screen.findByText("160 rekaman ditambahkan dari savedrecs.txt (format Web of Science)."),
    ).toBeInTheDocument();
    expect(screen.getByText("Rekaman ke-3: Rekaman tanpa judul (TI).")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/workspaces/ws1/imports/file");
    expect(onImported).toHaveBeenCalled();
  });

  it("shows the server error message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Format file tidak dikenali." }), { status: 422 }),
    );

    await upload();

    expect(await screen.findByRole("alert")).toHaveTextContent("Format file tidak dikenali.");
  });
});
