import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ImportPanel } from "./components/ImportPanel";
import { OpenAlexPanel } from "./components/OpenAlexPanel";

type Tab = "upload" | "openalex";

export default function App() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("upload");

  return (
    <main>
      <header>
        <h1>{t("app.title")}</h1>
        <p className="muted">{t("app.tagline")}</p>
      </header>
      <nav className="tabs" role="tablist">
        {(["upload", "openalex"] as const).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? "tab active" : "tab"}
            onClick={() => setTab(id)}
          >
            {t(`tabs.${id}`)}
          </button>
        ))}
      </nav>
      {/* Both panels stay mounted so switching tabs keeps their results. */}
      <div hidden={tab !== "upload"}>
        <ImportPanel />
      </div>
      <div hidden={tab !== "openalex"}>
        <OpenAlexPanel />
      </div>
    </main>
  );
}
