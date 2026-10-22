import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, countOpenAlex, importOpenAlex } from "../api";
import {
  WORK_TYPES,
  type OpenAlexCount,
  type OpenAlexImport,
  type OpenAlexQuery,
  type SearchScope,
  type WorkType,
} from "../types";
import { PreviewResult } from "./PreviewResult";

const PER_PAGE = 200;
// OpenAlex bills about US$0.001 per list request (one page of up to 200 works).
const USD_PER_PAGE = 0.001;

type State =
  | { status: "idle" }
  | { status: "counting" | "importing"; count?: OpenAlexCount }
  | { status: "counted"; count: OpenAlexCount }
  | { status: "imported"; count?: OpenAlexCount; result: OpenAlexImport }
  | { status: "error"; message: string; count?: OpenAlexCount };

function parseYear(value: string): number | null {
  const year = Number.parseInt(value, 10);
  return Number.isNaN(year) ? null : year;
}

export function OpenAlexPanel() {
  const { t } = useTranslation();
  const [terms, setTerms] = useState("");
  const [scope, setScope] = useState<SearchScope>("title_and_abstract");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [types, setTypes] = useState<WorkType[]>([]);
  const [languages, setLanguages] = useState("");
  const [openAccess, setOpenAccess] = useState(false);
  const [maxResults, setMaxResults] = useState(1000);
  // Kept in memory only: never persisted to storage.
  const [apiKey, setApiKey] = useState("");
  const [state, setState] = useState<State>({ status: "idle" });

  const query: OpenAlexQuery = {
    terms: terms.trim(),
    scope,
    year_from: parseYear(yearFrom),
    year_to: parseYear(yearTo),
    types,
    languages: languages
      .split(",")
      .map((code) => code.trim().toLowerCase())
      .filter(Boolean),
    open_access_only: openAccess,
    max_results: maxResults,
  };
  const busy = state.status === "counting" || state.status === "importing";
  const count = "count" in state ? state.count : undefined;
  const toImport = count ? Math.min(count.count, maxResults) : 0;

  function resetCount() {
    // Any edit makes the previous count stale.
    if (state.status !== "idle") setState({ status: "idle" });
  }

  function toggleType(type: WorkType) {
    setTypes((current) =>
      current.includes(type) ? current.filter((t) => t !== type) : [...current, type],
    );
    resetCount();
  }

  async function run<T>(status: "counting" | "importing", call: () => Promise<T>) {
    setState({ status, count });
    try {
      return await call();
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t("import.errorGeneric");
      setState({ status: "error", message, count });
      return null;
    }
  }

  async function handleCount(event: FormEvent) {
    event.preventDefault();
    const result = await run("counting", () => countOpenAlex(query, apiKey));
    if (result) setState({ status: "counted", count: result });
  }

  async function handleImport() {
    const result = await run("importing", () => importOpenAlex(query, apiKey));
    if (result) setState({ status: "imported", count, result });
  }

  return (
    <section>
      <h2>{t("openalex.heading")}</h2>
      <p className="muted">{t("openalex.help")}</p>

      <form className="query-form" onSubmit={handleCount} onChange={resetCount}>
        <label className="wide">
          {t("openalex.terms")}
          <input
            type="text"
            required
            value={terms}
            onChange={(e) => setTerms(e.target.value)}
            placeholder='motorcycle AND (helmet OR "head injury")'
          />
          <small className="muted">{t("openalex.termsHint")}</small>
        </label>

        <label>
          {t("openalex.scope")}
          <select value={scope} onChange={(e) => setScope(e.target.value as SearchScope)}>
            <option value="title_and_abstract">{t("openalex.scopeTitleAbstract")}</option>
            <option value="title">{t("openalex.scopeTitle")}</option>
            <option value="fulltext">{t("openalex.scopeFulltext")}</option>
          </select>
        </label>
        <label>
          {t("openalex.yearFrom")}
          <input
            type="number"
            min={1500}
            max={2100}
            value={yearFrom}
            onChange={(e) => setYearFrom(e.target.value)}
          />
        </label>
        <label>
          {t("openalex.yearTo")}
          <input
            type="number"
            min={1500}
            max={2100}
            value={yearTo}
            onChange={(e) => setYearTo(e.target.value)}
          />
        </label>

        <fieldset className="wide">
          <legend>{t("openalex.types")}</legend>
          {WORK_TYPES.map((type) => (
            <label key={type} className="check">
              <input
                type="checkbox"
                checked={types.includes(type)}
                onChange={() => toggleType(type)}
              />
              {t(`openalex.workType.${type}`)}
            </label>
          ))}
          <small className="muted">{t("openalex.typeAll")}</small>
        </fieldset>

        <label>
          {t("openalex.languages")}
          <input
            type="text"
            value={languages}
            onChange={(e) => setLanguages(e.target.value)}
            placeholder="en, id"
          />
          <small className="muted">{t("openalex.languagesHint")}</small>
        </label>
        <label>
          {t("openalex.maxResults")}
          <input
            type="number"
            min={1}
            max={5000}
            value={maxResults}
            onChange={(e) => setMaxResults(Number(e.target.value) || 1)}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={openAccess}
            onChange={(e) => setOpenAccess(e.target.checked)}
          />
          {t("openalex.openAccess")}
        </label>

        <label className="wide">
          {t("openalex.apiKey")}
          <input
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <small className="muted">{t("openalex.apiKeyHint")}</small>
        </label>

        <div className="wide">
          <button type="submit" disabled={busy || !query.terms}>
            {state.status === "counting" ? t("openalex.counting") : t("openalex.count")}
          </button>
        </div>
      </form>

      {count && (
        <div className="count-box">
          <p className="summary">{t("openalex.countResult", { count: count.count })}</p>
          <p>
            {t("openalex.estimate", {
              n: toImport,
              cost: (Math.ceil(toImport / PER_PAGE) * USD_PER_PAGE).toFixed(3),
            })}
          </p>
          <p className="muted">
            {t("openalex.queryUrl")}: <code>{count.query_url}</code>
          </p>
          {state.status !== "imported" && (
            <button type="button" onClick={handleImport} disabled={busy || toImport === 0}>
              {state.status === "importing"
                ? t("openalex.importing")
                : t("openalex.import", { n: toImport })}
            </button>
          )}
        </div>
      )}

      {state.status === "error" && (
        <p role="alert" className="error">
          {state.message}
        </p>
      )}
      {state.status === "imported" && (
        <>
          {state.result.truncated && (
            <p className="muted">{t("openalex.truncated", { max: maxResults })}</p>
          )}
          <PreviewResult
            result={state.result.result}
            summary={t("openalex.summary", {
              count: state.result.record_count,
              total: state.result.total_available,
            })}
          />
        </>
      )}
    </section>
  );
}
