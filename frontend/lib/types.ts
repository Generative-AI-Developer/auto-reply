export type RequestStatus = "Pending" | "Sent" | "Awaited" | "No Data Found";

export interface ResponseFile {
  id: number;
  original_filename: string;
  matched_date: string | null;
  received_at: string;
}

export interface RequestNumber {
  id: number;
  value: string;
  status: RequestStatus;
  files: ResponseFile[];
}

export interface RequestItem {
  id: number;
  request_id: string;
  request_number: string | null;
  owner_user_id: string;
  numbers: RequestNumber[];
  request_type: string;
  duration_days: number | null;
  case_officer: string;
  justification: string;
  request_date: string | null;
  created_at: string;
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
