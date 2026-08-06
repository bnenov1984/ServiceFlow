/** Tenant Employee Management (docs/business-os/18 §14, Etap 3): Owner-only
 * view/add/deactivate/reactivate on the existing `/api/v1/users` contract
 * (`identity/router.py`'s `users_router`) — no backend changes, this is the
 * frontend consumer that contract was always waiting for. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

interface Employee {
  id: string;
  name: string;
  email: string;
  is_owner: boolean;
  is_active: boolean;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 12;

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

export function EmployeesPage() {
  const { me, refresh } = useAuth();
  const queryClient = useQueryClient();

  const employees = useQuery({
    queryKey: queryKeys.employees(true),
    queryFn: () => api.get<Employee[]>("/users?include_inactive=true"),
    enabled: Boolean(me?.is_owner),
  });

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const [isOwner, setIsOwner] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [confirmDeactivateId, setConfirmDeactivateId] = useState<string | null>(null);
  const [confirmDemoteId, setConfirmDemoteId] = useState<string | null>(null);
  const [patchSubmittingId, setPatchSubmittingId] = useState<string | null>(null);
  const [patchError, setPatchError] = useState<string | null>(null);

  if (!me?.is_owner) {
    return (
      <section>
        <ErrorState text={t("employees.access_denied")} />
      </section>
    );
  }

  const afterMutation = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.employees(true) });
    void refresh();
  };

  const validate = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    if (name.trim().length === 0) errors.name = t("errors.validation");
    if (!EMAIL_RE.test(email)) errors.email = t("errors.validation");
    if (password.length < MIN_PASSWORD_LENGTH) errors.password = t("errors.validation");
    if (pin.length > 0 && (pin.length < 4 || pin.length > 20)) errors.pin = t("errors.validation");
    return errors;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;

    const clientErrors = validate();
    if (Object.keys(clientErrors).length > 0) {
      setFieldErrors(clientErrors);
      return;
    }

    setFieldErrors({});
    setFormError(null);
    setSubmitting(true);
    try {
      await api.post("/users", {
        name, email, password, is_owner: isOwner,
        pin: pin.length > 0 ? pin : undefined,
      });
      setName("");
      setEmail("");
      setPassword("");
      setPin("");
      setIsOwner(false);
      await afterMutation();
    } catch (err) {
      setPassword("");
      setFormError(errorText(err));
    } finally {
      setSubmitting(false);
    }
  };

  const setActive = async (id: string, isActive: boolean) => {
    if (patchSubmittingId) return;
    setPatchSubmittingId(id);
    setPatchError(null);
    try {
      await api.patch(`/users/${id}`, { is_active: isActive });
      setConfirmDeactivateId(null);
      await afterMutation();
    } catch (err) {
      setPatchError(errorText(err));
    } finally {
      setPatchSubmittingId(null);
    }
  };

  const setRole = async (id: string, nextIsOwner: boolean) => {
    if (patchSubmittingId) return;
    setPatchSubmittingId(id);
    setPatchError(null);
    try {
      await api.patch(`/users/${id}`, { is_owner: nextIsOwner });
      setConfirmDemoteId(null);
      await afterMutation();
    } catch (err) {
      setPatchError(errorText(err));
    } finally {
      setPatchSubmittingId(null);
    }
  };

  return (
    <section>
      <h1 className="mb-4 text-xl font-semibold text-slate-900">{t("employees.title")}</h1>

      <p className="mb-4 text-sm text-slate-600">
        {t("employees.seat_usage_label")}: {me.seat_usage}/{me.seat_limit ?? t("employees.seat_limit_unlimited")}
      </p>

      <form
        onSubmit={(e) => void onSubmit(e)}
        className="mb-6 flex max-w-lg flex-col gap-4 rounded-lg border border-slate-200 bg-white p-6"
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="employee-name">
            {t("employees.field_name")}
          </label>
          <input
            id="employee-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              fieldErrors.name ? "border-red-600" : "border-slate-300"
            }`}
          />
          {fieldErrors.name && (
            <p role="alert" className="mt-0.5 text-xs text-red-700">{fieldErrors.name}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="employee-email">
            {t("auth.email")}
          </label>
          <input
            id="employee-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              fieldErrors.email ? "border-red-600" : "border-slate-300"
            }`}
          />
          {fieldErrors.email && (
            <p role="alert" className="mt-0.5 text-xs text-red-700">{fieldErrors.email}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="employee-password">
            {t("auth.password")}
          </label>
          <input
            id="employee-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              fieldErrors.password ? "border-red-600" : "border-slate-300"
            }`}
          />
          {fieldErrors.password ? (
            <p role="alert" className="mt-0.5 text-xs text-red-700">{fieldErrors.password}</p>
          ) : (
            <p className="mt-0.5 text-xs text-slate-400">{t("employees.field_password_hint")}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="employee-pin">
            {t("employees.field_pin")}
          </label>
          <input
            id="employee-pin"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            className={`w-full rounded-lg border px-3 py-2 min-h-touch ${
              fieldErrors.pin ? "border-red-600" : "border-slate-300"
            }`}
          />
          {fieldErrors.pin ? (
            <p role="alert" className="mt-0.5 text-xs text-red-700">{fieldErrors.pin}</p>
          ) : (
            <p className="mt-0.5 text-xs text-slate-400">{t("employees.field_pin_hint")}</p>
          )}
        </div>

        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" checked={isOwner} onChange={(e) => setIsOwner(e.target.checked)} />
          {t("employees.owner_checkbox")}
        </label>

        {formError && <p role="alert" className="text-sm text-red-700">{formError}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50 min-h-touch"
        >
          {submitting ? t("common.loading") : t("employees.add_action")}
        </button>
      </form>

      {employees.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : employees.isError ? (
        <ErrorState text={errorText(employees.error)} onRetry={() => void employees.refetch()} />
      ) : employees.data && employees.data.length > 0 ? (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {employees.data.map((emp) => (
            <li key={emp.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div>
                <p className="font-medium text-slate-900">{emp.name}</p>
                <p className="text-sm text-slate-500">{emp.email}</p>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span className="text-slate-600">
                  {emp.is_owner ? t("employees.role_owner") : t("employees.role_worker")}
                </span>
                <span className={emp.is_active ? "text-green-700" : "text-slate-400"}>
                  {emp.is_active ? t("employees.status_active") : t("employees.status_inactive")}
                </span>
                {emp.is_owner ? (
                  <button
                    type="button"
                    disabled={patchSubmittingId === emp.id}
                    onClick={() => setConfirmDemoteId(emp.id)}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 min-h-touch"
                  >
                    {t("employees.demote_action")}
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={patchSubmittingId === emp.id}
                    onClick={() => void setRole(emp.id, true)}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 min-h-touch"
                  >
                    {t("employees.promote_action")}
                  </button>
                )}
                {emp.is_active ? (
                  <button
                    type="button"
                    disabled={patchSubmittingId === emp.id}
                    onClick={() => setConfirmDeactivateId(emp.id)}
                    className="rounded-lg border border-red-300 px-3 py-1.5 font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 min-h-touch"
                  >
                    {t("employees.deactivate_action")}
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={patchSubmittingId === emp.id}
                    onClick={() => void setActive(emp.id, true)}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 min-h-touch"
                  >
                    {t("employees.reactivate_action")}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState text={t("employees.empty")} />
      )}

      {/* Promote/reactivate have no confirm step (unconfirmed-additive, by
          design), so a failure there has no dialog to show it in - this
          stays visible for those paths. Deactivate/demote failures show
          inside their own ConfirmDialog instead (see the `error` prop
          below) and are suppressed here to avoid a duplicate. */}
      {patchError && confirmDeactivateId === null && confirmDemoteId === null && (
        <p role="alert" className="mt-2 text-sm text-red-700">{patchError}</p>
      )}

      <ConfirmDialog
        open={confirmDeactivateId !== null}
        title={t("employees.deactivate_confirm_title")}
        message={t("employees.deactivate_confirm_message")}
        error={confirmDeactivateId !== null ? patchError : null}
        onClose={() => {
          setConfirmDeactivateId(null);
          setPatchError(null);
        }}
        onConfirm={() => {
          if (confirmDeactivateId) void setActive(confirmDeactivateId, false);
        }}
        submitting={patchSubmittingId === confirmDeactivateId && confirmDeactivateId !== null}
      />

      <ConfirmDialog
        open={confirmDemoteId !== null}
        title={t("employees.demote_confirm_title")}
        message={t("employees.demote_confirm_message")}
        error={confirmDemoteId !== null ? patchError : null}
        onClose={() => {
          setConfirmDemoteId(null);
          setPatchError(null);
        }}
        onConfirm={() => {
          if (confirmDemoteId) void setRole(confirmDemoteId, false);
        }}
        submitting={patchSubmittingId === confirmDemoteId && confirmDemoteId !== null}
      />
    </section>
  );
}
