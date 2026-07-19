export interface PsClient {
  id: string;
  name: string;
  kind: "person" | "company";
}

export interface PsAssignment {
  id: string;
  client_id: string;
  title: string;
  stage: "intake" | "in_progress" | "waiting_client" | "delivered";
  lifecycle_state: "active" | "delivered" | "cancelled";
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
