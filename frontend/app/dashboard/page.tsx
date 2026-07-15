"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Topbar from "@/components/Topbar";
import RequestsTable from "@/components/RequestsTable";
import {
  addUser,
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

  // Add user form
  const [newUserId, setNewUserId] = useState("");
  const [zone, setZone] = useState("");
  const [password, setPassword] = useState("");
  const [userMsg, setUserMsg] = useState("");
  const [userErr, setUserErr] = useState("");

  const refresh = useCallback(async () => {
    try {
      setRequests(await listRequests({ q, status_filter: statusFilter }));
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
      <Topbar subtitle="Server Dashboard" />
      <div className="container">
        <div className="card">
          <h2>Add User</h2>
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
            <button type="submit">Create User</button>
            {userMsg && <div className="ok">{userMsg}</div>}
            {userErr && <div className="error">{userErr}</div>}
          </form>
        </div>

        <div className="card">
          <h2>All Requests (live)</h2>
          <div className="row search">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="🔍 Search by Request ID or number (mobile / NIC / any)…"
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
          </div>
          {err && <div className="error">{err}</div>}
          <RequestsTable requests={requests} showOwner onStatusChange={onStatusChange} />
        </div>
      </div>
    </>
  );
}
