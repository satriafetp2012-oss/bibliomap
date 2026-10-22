import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import id from "./locales/id.json";

// Bahasa Indonesia is the only UI language for now; add more resources here.
void i18n.use(initReactI18next).init({
  resources: { id: { translation: id } },
  lng: "id",
  fallbackLng: "id",
  interpolation: { escapeValue: false }, // React already escapes output.
});

export default i18n;
