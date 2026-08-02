import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Dialog } from "../../components/Dialog";
import { t } from "../../i18n/bg";
import { ApiError, api } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import type { PsClient } from "../types";

export function NewClientDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"person" | "company">("person");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const close = () => {
    onClose();
    setName("");
    setKind("person");
    setError(null);
  };

  const submit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post<PsClient>("/ps/clients", { name: name.trim(), kind });
      await queryClient.invalidateQueries({ queryKey: queryKeys.psClients });
      close();
    } catch (err) {
      setError(err instanceof ApiError ? t(err.messageKey, err.params) : t("errors.internal"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} title={t("ps.new_client_dialog_title")}>
      <div className="flex flex-col gap-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="new-client-name">
            {t("ps.client_name_label")}
          </label>
          <input
            id="new-client-name"
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("ps.client_name_placeholder")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="new-client-kind">
            {t("ps.client_kind_label")}
          </label>
          <select
            id="new-client-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as "person" | "company")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-touch"
          >
            <option value="person">{t("ps.client_kind_person")}</option>
            <option value="company">{t("ps.client_kind_company")}</option>
          </select>
        </div>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || !name.trim()}
            onClick={() => void submit()}
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
          >
            {submitting ? t("common.loading") : t("ps.client_add")}
          </button>
          <button
            type="button"
            onClick={close}
            className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-50 min-h-touch"
          >
            {t("common.cancel")}
          </button>
        </div>
      </div>
    </Dialog>
  );
}
