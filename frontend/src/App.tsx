import { useState } from "react";
import { useTranslation } from "react-i18next";

import { DedupPanel } from "./components/DedupPanel";
import { FilterPanel } from "./components/FilterPanel";
import { ImportList } from "./components/ImportList";
import { ImportPanel } from "./components/ImportPanel";
import { OpenAlexPanel } from "./components/OpenAlexPanel";
import { PrismaDiagram } from "./components/PrismaDiagram";
import { useWorkspace } from "./useWorkspace";

const TABS = ["import", "dedup", "data", "prisma"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const { t } = useTranslation();
  const { summary, notice, reload, startNew } = useWorkspace();
  const [tab, setTab] = useState<Tab>("import");

  if (!summary) {
    return (
      <main>
        <h1>{t("app.title")}</h1>
        <p role="status">{t("workspace.loading")}</p>
      </main>
    );
  }

  const { workspace, counts, imports } = summary;
  const badge = (name: Tab) =>
    name === "dedup" && counts.pending_reviews > 0 ? ` (${counts.pending_reviews})` : "";

  return (
    <main>
      <header>
        <h1>{t("app.title")}</h1>
        <p className="muted">{t("app.tagline")}</p>
        {notice && <p role="status">{t(notice)}</p>}
        <p className="summary">
          {t("workspace.summary", {
            identified: counts.identified,
            unique: counts.unique,
            duplicates: counts.duplicates_removed,
            kept: counts.kept,
          })}
        </p>
        <p className="muted">
          {t("workspace.linkHint")}{" "}
          <button type="button" className="link" onClick={() => void startNew()}>
            {t("workspace.newWorkspace")}
          </button>
        </p>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            className={tab === name ? "tab active" : "tab"}
            onClick={() => setTab(name)}
          >
            {t(`tabs.${name}`)}
            {badge(name)}
          </button>
        ))}
      </nav>

      {/* Import panels stay mounted so a long OpenAlex form is not lost. */}
      <div hidden={tab !== "import"}>
        <ImportPanel workspaceId={workspace.id} onImported={() => void reload()} />
        <OpenAlexPanel workspaceId={workspace.id} onImported={() => void reload()} />
        <ImportList
          workspaceId={workspace.id}
          imports={imports}
          onChanged={() => void reload()}
        />
      </div>
      {tab === "dedup" && (
        <DedupPanel
          workspaceId={workspace.id}
          autoRemoved={counts.duplicates_removed}
          active
          onChanged={() => void reload()}
        />
      )}
      {tab === "data" && (
        <FilterPanel
          workspaceId={workspace.id}
          filters={workspace.filters}
          version={workspace.version}
          counts={{ kept: counts.kept, excluded: counts.excluded }}
          onChanged={() => void reload()}
        />
      )}
      {tab === "prisma" && (
        <PrismaDiagram workspaceId={workspace.id} version={workspace.version} />
      )}
    </main>
  );
}
