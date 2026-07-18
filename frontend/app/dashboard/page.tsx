"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Topbar from "@/components/Topbar";
import RequestsTable from "@/components/RequestsTable";
import {
  addUser,
  exportRequests,
  getSession,
  listRequests,
  requestsSocket,
  updateNumberStatus,
} from "@/lib/api";
import { RequestItem } from "@/lib/types";

const STATUS_OPTIONS = ["", "Pending", "Sent", "Awaited", "No Data Found"];

export default function DashboardPage() {
  const router = useRouter();
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Add user form
  const [newUserId, setNewUserId] = useState("");
  const [zone, setZone] = useState("");
  const [password, setPassword] = useState("");
  const [userMsg, setUserMsg] = useState("");
  const [userErr, setUserErr] = useState("");

  const refresh = useCallback(async () => {
    try {
      const items = await listRequests({ q, status_filter: statusFilter });
      setRequests(items);
      // Drop selected rows that are no longer visible so a stale selection
      // can't silently end up in an export.
      const visible = new Set(items.flatMap((r) => r.numbers.map((n) => n.id)));
      setSelected((prev) => new Set([...prev].filter((id) => visible.has(id))));
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [q, statusFilter]);

  useEffect(() => {
    const s = getSession();
    if (!s) {
      router.replace("/login");
      return;
    }
    if (s.role !== "admin") {
      router.replace("/client");
      return;
    }
    refresh();
    const ws = requestsSocket(() => refresh());
    return () => ws?.close();
  }, [refresh, router]);

  async function onStatusChange(requestId: string, identifierId: number, status: string) {
    try {
      await updateNumberStatus(requestId, identifierId, status);
      refresh();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function onExport() {
    setErr("");
    const ids =
      selected.size > 0
        ? [...selected]
        : requests.flatMap((r) => r.numbers.map((n) => n.id));
    if (ids.length === 0) {
      setErr("Nothing to export.");
      return;
    }
    try {
      const blob = await exportRequests(ids);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `requests-export-${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      setSelected(new Set());
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function onAddUser(e: FormEvent) {
    e.preventDefault();
    setUserMsg("");
    setUserErr("");
    try {
      const u = await addUser({ user_id: newUserId.trim(), zone_section: zone, password });
      setUserMsg(`Created user ${u.user_id}`);
      setNewUserId("");
      setZone("");
      setPassword("");
    } catch (e) {
      setUserErr((e as Error).message);
    }
  }

  return (
    <>
      <Topbar subtitle="ADMIN DASHBOARD" />
      <div className="container">
        <div className="card">
          <h2 style={{ textAlign: "center" }}>Add User</h2>
          <form onSubmit={onAddUser}>
            <div className="row">
              <div className="field">
                <label>User ID</label>
                <input value={newUserId} onChange={(e) => setNewUserId(e.target.value)} />
              </div>
              <div className="field">
                <label>Zone / Section</label>
                <input value={zone} onChange={(e) => setZone(e.target.value)} />
              </div>
              <div className="field">
                <label>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <button type="submit">Create User</button>
            </div>
            {userMsg && <div className="ok">{userMsg}</div>}
            {userErr && <div className="error">{userErr}</div>}
          </form>
        </div>

        <div className="card">
          <h2 style={{ textAlign: "center" }}>All Requests (live)</h2>
          <div className="row search">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="🔍 Search by Request Number or Mobile/CNIC/IMEI No…"
            />
            <select
              style={{ flex: "0 0 200px" }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s || "All statuses"}
                </option>
              ))}
            </select>
            <button type="button" style={{ flex: "0 0 auto" }} onClick={onExport}>
              Export to Excel{selected.size > 0 ? ` (${selected.size} selected)` : ""}
            </button>
          </div>
          <p className="muted">
            Click rows to select them (Shift+click for a range), then Export to Excel. With
            nothing selected, all rows currently shown are exported. Double-click any cell to
            copy its value.
          </p>
          {err && <div className="error">{err}</div>}
          <RequestsTable
            requests={requests}
            showOwner
            onStatusChange={onStatusChange}
            selectable
            selected={selected}
            onSelect={setSelected}
          />
        </div>
      </div>
    </>
  );
}
