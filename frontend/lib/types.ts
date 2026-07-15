export interface ResponseFile {
  id: number;
  original_filename: string;
  matched_value: string;
  matched_date: string | null;
  received_at: string;
}

export interface RequestItem {
  id: number;
  request_id: string;
  owner_user_id: string;
  numbers: string[];
  duration_days: number | null;
  case_officer: string;
  justification: string;
  request_date: string | null;
  status: "Pending" | "Sent" | "Awaited" | "No Data Found";
  created_at: string;
  files: ResponseFile[];
}

export interface UserItem {
  id: number;
  user_id: string;
  zone_section: string;
  role: string;
  created_at: string;
}

export interface Session {
  token: string;
  user_id: string;
  role: string;
}

export interface ImportResultShape {
  created: number;
  failed: number;
  errors: string[];
}

export const MANUAL_STATUSES = ["Awaited", "No Data Found"] as const;
