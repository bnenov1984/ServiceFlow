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
