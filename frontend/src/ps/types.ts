export interface PsClient {
  id: string;
  name: string;
  kind: "person" | "company";
}

export type PsStageCategory = "work" | "waiting_client" | "waiting_documents" | "review" | "delivery";

export interface PsStage {
  id: string;
  name: string;
  category: PsStageCategory;
  sort: number;
}

export interface PsWorkflowTemplate {
  id: string;
  name: string;
  is_active: boolean;
  stages: PsStage[];
}

export interface PsAssignment {
  id: string;
  client_id: string;
  title: string;
  lifecycle_state: "active" | "delivered" | "completed" | "cancelled";
  current_stage: PsStage | null;
  official_deadline_on: string | null;
  internal_target_on: string | null;
}

export interface PsNextAction {
  id: string;
  assignment_id: string;
  title: string;
  owner_user_id: string;
  due_on: string;
  completed: boolean;
  risk: "done" | "overdue" | "attention" | "ok";
}
