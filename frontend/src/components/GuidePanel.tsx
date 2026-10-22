import { useTranslation } from "react-i18next";

const GUIDE_URL =
  "https://github.com/satriafetp2012-oss/bibliomap/blob/main/docs/panduan-pengguna.md";

interface Step {
  title: string;
  body: string;
  items: string[];
}

interface Trouble {
  q: string;
  a: string;
}

export function GuidePanel() {
  const { t } = useTranslation();
  // The guide is data in the locale file, so translating it needs no code.
  const steps = t("guide.steps", { returnObjects: true }) as Step[];
  const methods = t("guide.methods", { returnObjects: true }) as string[];
  const trouble = t("guide.trouble", { returnObjects: true }) as Trouble[];

  return (
    <section className="guide">
      <h2>{t("guide.heading")}</h2>
      <p className="muted">{t("guide.intro")}</p>
      <p>
        <a href={GUIDE_URL} target="_blank" rel="noreferrer">
          {t("guide.full")}
        </a>
      </p>

      <ol className="steps">
        {steps.map((step, index) => (
          <li key={step.title}>
            <h3>
              <span className="step-number">{index + 1}</span>
              {step.title}
            </h3>
            <p>{step.body}</p>
            <ul>
              {step.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>

      <h3>{t("guide.methodsHeading")}</h3>
      <p>{t("guide.methodsIntro")}</p>
      <ol>
        {methods.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ol>

      <h3>{t("guide.troubleHeading")}</h3>
      <dl className="trouble">
        {trouble.map((item) => (
          <div key={item.q}>
            <dt>{item.q}</dt>
            <dd>{item.a}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
