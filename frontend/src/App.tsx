import { useEffect, useState } from "react";
import { t } from "./i18n/bg";

type HealthStatus = "checking" | "ok" | "degraded" | "fail" | "unreachable";

export function App() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    fetch("/api/v1/platform/health")
      .then((r) => r.json())
      .then((body: { status: "ok" | "degraded" | "fail" }) => setStatus(body.status))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", maxWidth: 640, margin: "4rem auto", padding: "0 1rem" }}>
      <h1>{t("app.name")}</h1>
      <p>{t(`health.${status}`)}</p>
    </main>
  );
}
