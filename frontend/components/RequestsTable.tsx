"use client";

import { MANUAL_STATUSES, RequestItem, RequestNumber } from "@/lib/types";

function statusClass(status: string): string {
  if (status === "No Data Found") return "NoData";
  return status;
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

interface Row {
  request: RequestItem;
  number: RequestNumber | null;
}

export default function RequestsTable({
  requests,
  showOwner = false,
  onStatusChange,
}: {
  requests: RequestItem[];
  showOwner?: boolean;
  onStatusChange?: (requestId: string, identifierId: number, status: string) => void;
}) {
  const rows: Row[] = requests.flatMap((r) =>
    r.numbers.length > 0
      ? r.numbers.map((n): Row => ({ request: r, number: n }))
      : [{ request: r, number: null }]
  );

  if (rows.length === 0) {
    return <p className="muted">No requests found.</p>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            {showOwner && <th>User</th>}
            <th>Request ID</th>
            <th>Number</th>
            <th>Request Type</th>
            <th>Days</th>
            <th>Case Officer</th>
            <th>Justification</th>
            <th>Date</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ request: r, number: n }) => (
            <tr key={n ? n.id : r.id}>
              {showOwner && <td>{r.owner_user_id}</td>}
              <td>{r.request_id}</td>
              <td>{n ? n.value : "—"}</td>
              <td>{r.request_type || "—"}</td>
              <td>{r.duration_days ?? "—"}</td>
              <td>{r.case_officer || "—"}</td>
              <td>{r.justification || "—"}</td>
              <td>{formatDateTime(r.created_at)}</td>
              <td>
                {n && onStatusChange ? (
                  <select
                    value={MANUAL_STATUSES.includes(n.status as never) ? n.status : ""}
                    onChange={(e) => e.target.value && onStatusChange(r.request_id, n.id, e.target.value)}
                  >
                    <option value="">{n.status}</option>
                    {MANUAL_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                ) : n ? (
                  <span className={`status ${statusClass(n.status)}`}>{n.status}</span>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
