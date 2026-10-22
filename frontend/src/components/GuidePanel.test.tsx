import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GuidePanel } from "./GuidePanel";

describe("GuidePanel", () => {
  it("renders every step from the locale, in order", () => {
    render(<GuidePanel />);

    const steps = screen.getAllByRole("listitem").filter((li) => li.querySelector("h3"));
    expect(steps).toHaveLength(6);
    expect(within(steps[0]).getByRole("heading")).toHaveTextContent("Siapkan ekspor yang lengkap");
    expect(within(steps[5]).getByRole("heading")).toHaveTextContent("Ekspor");
    // Each step is numbered for the reader.
    expect(within(steps[0]).getByText("1")).toBeInTheDocument();
  });

  it("covers the gotchas researchers hit", () => {
    render(<GuidePanel />);

    expect(screen.getAllByText(/Full Record and Cited References/).length).toBeGreaterThan(0);
    expect(screen.getByText(/satu-satunya cara membuka kembali workspace/)).toBeInTheDocument();
    expect(screen.getByText(/Tekan D untuk duplikat/)).toBeInTheDocument();
    expect(screen.getByText(/tidak tersaring oleh filter tahun/)).toBeInTheDocument();
  });

  it("lists what to report in the methods section", () => {
    render(<GuidePanel />);

    expect(screen.getByRole("heading", { name: /bagian Metode/ })).toBeInTheDocument();
    expect(screen.getByText(/Basis data dan tanggal pencarian/)).toBeInTheDocument();
    expect(screen.getByText(/algoritma Leiden/)).toBeInTheDocument();
  });

  it("answers the common problems", () => {
    render(<GuidePanel />);

    expect(screen.getByText("Format file tidak dikenali")).toBeInTheDocument();
    expect(screen.getByText(/openalex.org\/settings\/api/)).toBeInTheDocument();
    expect(screen.getByText("Workspace hilang")).toBeInTheDocument();
  });

  it("links to the full guide", () => {
    render(<GuidePanel />);

    const link = screen.getByRole("link", { name: "Baca panduan lengkap" });
    expect(link).toHaveAttribute("href", expect.stringContaining("panduan-pengguna.md"));
    expect(link).toHaveAttribute("rel", "noreferrer");
  });
});
