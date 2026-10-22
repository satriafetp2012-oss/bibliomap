import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, workspaceApi } from "../api";
import type { PendingPage, RecordView } from "../types";

interface Props {
  workspaceId: string;
  autoRemoved: number;
  /** Only the visible tab listens to keyboard shortcuts. */
  active: boolean;
  onChanged: () => void;
}

type Field = { key: string; value: (r: RecordView) => string };

const FIELDS: Field[] = [
  { key: "source", value: (r) => r.import_label },
  {
    key: "authors",
    value: (r) => r.authors.join("; ") + (r.author_count > r.authors.length ? " …" : ""),
  },
  { key: "year", value: (r) => String(r.year ?? "") },
  { key: "journal", value: (r) => r.source_title ?? "" },
  { key: "doi", value: (r) => r.doi ?? "" },
  { key: "volume", value: (r) => [r.volume, r.issue, r.pages].map((v) => v ?? "–").join(" / ") },
  { key: "abstract", value: (r) => r.abstract ?? "" },
];

export function DedupPanel({ workspaceId, autoRemoved, active, onChanged }: Props) {
  const { t } = useTranslation();
  const [page, setPage] = useState<PendingPage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<{ a: number; b: number } | null>(null);

  const load = useCallback(async () => {
    setPage(await workspaceApi.pending(workspaceId));
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load, autoRemoved]);

  const pair = page?.items[0];

  const act = useCallback(
    async (call: () => Promise<void>, remember: { a: number; b: number } | null) => {
      setBusy(true);
      setError(null);
      try {
        await call();
        setLast(remember);
        await load();
        onChanged();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("import.errorGeneric"));
      } finally {
        setBusy(false);
      }
    },
    [load, onChanged, t],
  );

  const decide = useCallback(
    (same: boolean) => {
      if (!pair || busy) return;
      const ids = { a: pair.a.id, b: pair.b.id };
      void act(() => workspaceApi.decide(workspaceId, ids.a, ids.b, same), ids);
    },
    [pair, busy, act, workspaceId],
  );

  useEffect(() => {
    if (!active) return;
    function onKey(event: KeyboardEvent) {
      // Never hijack typing in a form field.
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (event.key === "d" || event.key === "D") decide(true);
      if (event.key === "n" || event.key === "N") decide(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, decide]);

  return (
    <section>
      <h2>{t("dedup.heading")}</h2>
      <p>{t("dedup.auto", { count: autoRemoved })}</p>
      {page && (
        <p className="summary">
          {page.total > 0 ? t("dedup.remaining", { count: page.total }) : t("dedup.done")}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {pair && (
        <div className="pair">
          <p className="muted">
            {t("dedup.similarity", { value: pair.title_similarity })}
            {pair.reasons
              .filter((r) => !r.startsWith("title:"))
              .map((r) => ` · ${t(`dedup.reasons.${r}`)}`)
              .join("")}
          </p>
          <table className="pair-table">
            <thead>
              <tr>
                <th />
                <th>{pair.a.title}</th>
                <th>{pair.b.title}</th>
              </tr>
            </thead>
            <tbody>
              {FIELDS.map((field) => {
                const a = field.value(pair.a);
                const b = field.value(pair.b);
                return (
                  <tr key={field.key}>
                    <th scope="row">{t(`dedup.fields.${field.key}`)}</th>
                    <td className={a !== b && field.key !== "source" ? "diff" : undefined}>{a || "–"}</td>
                    <td className={a !== b && field.key !== "source" ? "diff" : undefined}>{b || "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="actions">
            <button type="button" disabled={busy} onClick={() => decide(true)}>
              {t("dedup.same")}
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => decide(false)}>
              {t("dedup.different")}
            </button>
            <span className="muted">{t("dedup.shortcuts")}</span>
          </div>
        </div>
      )}
      {last && (
        <button
          type="button"
          className="link"
          disabled={busy}
          onClick={() => void act(() => workspaceApi.undoDecision(workspaceId, last.a, last.b), null)}
        >
          {t("dedup.undo")}
        </button>
      )}
    </section>
  );
}
