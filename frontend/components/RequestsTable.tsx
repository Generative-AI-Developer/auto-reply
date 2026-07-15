"use client";

import { MANUAL_STATUSES, RequestItem } from "@/lib/types";

function statusClass(status: string): string {
  if (status === "No Data Found") return "NoData";
  return status;
}

export default function RequestsTable({
  requests,
  showOwner = false,
  onStatusChange,
}: {
  requests: RequestItem[];
  showOwner?: boolean;
  onStatusChange?: (requestId: string, status: string) => void;
}) {
  if (requests.length === 0) {
    return <p className="muted">No requests found.</p>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            <th>Request ID</th>
            {showOwner && <th>User</th>}
            <th>Numbers</th>
            <th>Days</th>
            <th>Case Officer</th>
            <th>Justification</th>
            <th>Date</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((r) => (
            <tr key={r.id}>
              <td>{r.request_id}</td>
              {showOwner && <td>{r.owner_user_id}</td>}
              <td>{r.numbers.join(", ")}</td>
              <td>{r.duration_days ?? "—"}</td>
              <td>{r.case_officer || "—"}</td>
              <td>{r.justification || "—"}</td>
              <td>{r.request_date || "—"}</td>
              <td>
                {onStatusChange ? (
                  <select
                    value={MANUAL_STATUSES.includes(r.status as never) ? r.status : ""}
                    onChange={(e) => e.target.value && onStatusChange(r.request_id, e.target.value)}
                  >
                    <option value="">
                      {r.status}
                      {r.status === "Sent" || r.status === "Pending" ? " (auto)" : ""}
                    </option>
                    {MANUAL_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        Set: {s}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className={`status ${statusClass(r.status)}`}>{r.status}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
