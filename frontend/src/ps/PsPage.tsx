/**
 * PropertyFlow dashboard (docs/business-os PropertyFlow task): client-oriented
 * CRM-style screen — Клиенти | Ангажименти на избрания клиент | Следващи
 * действия на избрания ангажимент, plus a bottom detail panel for the
 * selected engagement. Existing API endpoints only, no new backend
 * functionality — fields the mockup shows but the data model doesn't have
 * (property/address, engagement "type", a single assignment owner) are
 * dropped rather than fabricated; see AssignmentDetailPanel's doc comment.
 */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AssignmentDetailPanel } from "./AssignmentDetailPanel";
import { AssignmentsColumn } from "./AssignmentsColumn";
import { ClientsColumn } from "./ClientsColumn";
import { NewAssignmentDialog } from "./dialogs/NewAssignmentDialog";
import { NextActionsColumn } from "./NextActionsColumn";
import { PsToolbar } from "./PsToolbar";
import { t } from "../i18n/bg";
import { ApiError, api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type {
  PsAssignment,
  PsClient,
  PsNextAction,
  PsUser,
  PsWorkflowTemplate,
} from "./types";

function errorText(error: unknown): string {
  return error instanceof ApiError ? t(error.messageKey, error.params) : t("errors.internal");
}

export function PsPage() {
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<string | null>(null);
  const [activeOnly, setActiveOnly] = useState(false);
  const [newAssignmentOpen, setNewAssignmentOpen] = useState(false);

  const clients = useQuery({
    queryKey: queryKeys.psClients,
    queryFn: () => api.get<PsClient[]>("/ps/clients"),
  });
  const assignmentsQuery = useQuery({
    queryKey: queryKeys.psAssignments,
    queryFn: () => api.get<PsAssignment[]>("/ps/assignments"),
  });
  const actions = useQuery({
    queryKey: queryKeys.psNextActions,
    queryFn: () => api.get<PsNextAction[]>("/ps/next-actions"),
  });
  const templates = useQuery({
    queryKey: queryKeys.psWorkflowTemplates,
    queryFn: () => api.get<PsWorkflowTemplate[]>("/ps/workflow-templates"),
  });
  const users = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.get<PsUser[]>("/users"),
  });

  const allAssignments = assignmentsQuery.data ?? [];
  const assignments = activeOnly
    ? allAssignments.filter((a) => a.lifecycle_state === "active")
    : allAssignments;

  const selectedClient = clients.data?.find((c) => c.id === selectedClientId) ?? null;
  const selectedAssignment = assignments.find((a) => a.id === selectedAssignmentId) ?? null;

  const selectClient = (client: PsClient) => {
    setSelectedClientId(client.id);
    setSelectedAssignmentId(null);
  };

  const selectAssignment = (assignment: PsAssignment) => {
    setSelectedClientId(assignment.client_id);
    setSelectedAssignmentId(assignment.id);
  };

  return (
    <div className="flex flex-col gap-4">
      <PsToolbar
        activeOnly={activeOnly}
        onToggleActiveOnly={() => setActiveOnly((v) => !v)}
        onNewAssignment={() => setNewAssignmentOpen(true)}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ClientsColumn
          clients={clients.data}
          assignments={assignments}
          isLoading={clients.isLoading}
          isError={clients.isError}
          errorText={errorText(clients.error)}
          onRetry={() => void clients.refetch()}
          selectedClientId={selectedClientId}
          onSelectClient={selectClient}
        />
        <AssignmentsColumn
          client={selectedClient}
          assignments={assignments}
          actions={actions.data ?? []}
          isLoading={assignmentsQuery.isLoading}
          isError={assignmentsQuery.isError}
          errorText={errorText(assignmentsQuery.error)}
          onRetry={() => void assignmentsQuery.refetch()}
          selectedAssignmentId={selectedAssignmentId}
          onSelectAssignment={selectAssignment}
          onAddClick={() => setNewAssignmentOpen(true)}
        />
        <NextActionsColumn
          assignment={selectedAssignment}
          actions={actions.data ?? []}
          users={users.data ?? []}
          isLoading={actions.isLoading}
          isError={actions.isError}
          errorText={errorText(actions.error)}
          onRetry={() => void actions.refetch()}
        />
      </div>

      <AssignmentDetailPanel assignment={selectedAssignment} client={selectedClient} />

      <NewAssignmentDialog
        open={newAssignmentOpen}
        onClose={() => setNewAssignmentOpen(false)}
        clients={clients.data ?? []}
        templates={templates.data ?? []}
        defaultClientId={selectedClientId}
        onCreated={selectAssignment}
      />
    </div>
  );
}
