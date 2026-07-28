export interface VendorMe {
  platform_admin_id: string;
  name: string;
  email: string;
  csrf_token: string;
}

export interface CompanySummary {
  id: string;
  name: string;
  business_profile: string;
  active_modules: string[];
  subscription_state: string;
  trial_ends_at: string | null;
  seat_limit: number | null;
  seat_usage: number;
  created_at: string;
}

export interface CompanyDetail extends CompanySummary {
  subscription_state_changed_at: string;
}

export interface ProvisionCompanyRequest {
  company_name: string;
  owner_name: string;
  owner_email: string;
  owner_password: string;
  business_profile: string;
  modules: string[];
}

export interface ProvisionCompanyResult {
  company_id: string;
  owner_id: string;
  subscription_state: string;
  trial_ends_at: string;
  business_profile: string;
  activated_modules: string[];
  audit_id: string;
}

export interface EntitlementResult {
  company_id: string;
  module_key: string;
  active_modules: string[];
  changed: boolean;
  audit_id: string;
}

export interface SubscriptionTransitionResult {
  company_id: string;
  old_state: string;
  new_state: string;
  reason: string;
  audit_id: string;
}

export interface SeatLimitResult {
  company_id: string;
  seat_limit: number | null;
  changed: boolean;
  audit_id: string;
}
