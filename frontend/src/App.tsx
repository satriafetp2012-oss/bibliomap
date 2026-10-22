import { useTranslation } from "react-i18next";

import { ImportPanel } from "./components/ImportPanel";

export default function App() {
  const { t } = useTranslation();
  return (
    <main>
      <header>
        <h1>{t("app.title")}</h1>
        <p className="muted">{t("app.tagline")}</p>
      </header>
      <ImportPanel />
    </main>
  );
}
