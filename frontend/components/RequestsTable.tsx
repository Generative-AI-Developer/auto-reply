"use client";

import { useRef } from "react";
import { MANUAL_STATUSES, RequestItem, RequestNumber } from "@/lib/types";

function statusClass(status: string): string {
  if (status === "No Data Found") return "NoData";
  return status;
}

// The underlying status stays "Sent" (used for matching/filtering); only the
// client-facing label changes, since from the requester's point of view the
// response has been received, not sent.
function displayStatus(status: string, perspective: "admin" | "client"): string {
  if (perspective === "client" && status === "Sent") return "Received";
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
  perspective = "admin",
  selectable = false,
  selected,
  onSelect,
}: {
  requests: RequestItem[];
  showOwner?: boolean;
  onStatusChange?: (requestId: string, identifierId: number, status: string) => void;
  perspective?: "admin" | "client";
  selectable?: boolean;
  selected?: Set<number>;
  onSelect?: (next: Set<number>) => void;
}) {
  // Anchor for shift+click range selection: the identifier id last clicked.
  const lastClickedRef = useRef<number | null>(null);

  const rows: Row[] = requests.flatMap((r) =>
    r.numbers.length > 0
      ? r.numbers.map((n): Row => ({ request: r, number: n }))
      : [{ request: r, number: null }]
  );

  function handleRowClick(identifierId: number, shiftKey: boolean) {
    if (!selectable || !onSelect) return;
    const next = new Set(selected ?? []);
    const anchor = lastClickedRef.current;
    if (shiftKey && anchor !== null && anchor !== identifierId) {
      const ids = rows.filter((row) => row.number).map((row) => row.number!.id);
      const a = ids.indexOf(anchor);
      const b = ids.indexOf(identifierId);
      if (a !== -1 && b !== -1) {
        for (let i = Math.min(a, b); i <= Math.max(a, b); i++) next.add(ids[i]);
      } else {
        next.add(identifierId);
      }
    } else if (next.has(identifierId)) {
      next.delete(identifierId);
    } else {
      next.add(identifierId);
    }
    lastClickedRef.current = identifierId;
    onSelect(next);
  }

  // Double-click any cell copies its text (rows use user-select:none when
  // selectable, so native text selection isn't available there). The two
  // clicks of a double-click toggle row selection on and off again, so the
  // selection state is left untouched.
  function handleCellCopy(e: React.MouseEvent<HTMLTableSectionElement>) {
    const td = (e.target as HTMLElement).closest("td");
    if (!td || td.querySelector("select")) return;
    const text = td.innerText.trim();
    if (!text || text === "—") return;
    navigator.clipboard?.writeText(text);
    td.classList.add("copied");
    setTimeout(() => td.classList.remove("copied"), 700);
  }

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
            <th>Request Number</th>
            <th>Mobile/CNIC/IMEI No</th>
            <th>Network</th>
            <th>Request Type</th>
            <th>Days</th>
            <th>Case Officer</th>
            <th>Justification</th>
            <th>Date/Time</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody onDoubleClick={handleCellCopy}>
          {rows.map(({ request: r, number: n }) => (
            <tr
              key={n ? n.id : r.id}
              className={
                selectable && n
                  ? `selectable${selected?.has(n.id) ? " selected" : ""}`
                  : undefined
              }
              onClick={(e) => n && handleRowClick(n.id, e.shiftKey)}
            >
              {showOwner && <td>{r.owner_user_id}</td>}
              <td>{r.request_id}</td>
              <td>{r.request_number || "—"}</td>
              <td>{n ? n.value : "—"}</td>
              <td>
                {(n ? n.network : r.network) || "—"}
                {n && n.part ? (
                  <span
                    style={{
                      marginLeft: 6,
                      fontSize: "0.72em",
                      padding: "1px 6px",
                      borderRadius: 4,
                      background: "#1f4e79",
                      color: "#fff",
                      whiteSpace: "nowrap",
                    }}
                  >
                    Set {n.part}/2
                  </span>
                ) : null}
              </td>
              <td>{(n ? n.request_type : r.request_type) || "—"}</td>
              <td>{(n ? n.duration_days : r.duration_days) ?? "—"}</td>
              <td>{r.case_officer || "—"}</td>
              <td>{r.justification || "—"}</td>
              <td>{formatDateTime(r.created_at)}</td>
              <td>
                {n && onStatusChange ? (
                  <select
                    onClick={(e) => e.stopPropagation()}
                    value={MANUAL_STATUSES.includes(n.status as never) ? n.status : ""}
                    onChange={(e) => e.target.value && onStatusChange(r.request_id, n.id, e.target.value)}
                  >
                    <option value="">{displayStatus(n.status, perspective)}</option>
                    {MANUAL_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                ) : n ? (
                  <span className={`status ${statusClass(n.status)}`}>
                    {displayStatus(n.status, perspective)}
                  </span>
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
