"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Topbar from "@/components/Topbar";
import RequestsTable from "@/components/RequestsTable";
import { getSession, importRequests, listRequests, requestsSocket } from "@/lib/api";
import { RequestItem } from "@/lib/types";

// Filter-only options. The backend value stays "Sent"; clients see it as
// "Received" everywhere, so the label matches the table's client perspective.
const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "Pending", label: "Pending" },
  { value: "Sent", label: "Received" },
  { value: "Awaited", label: "Awaited" },
  { value: "No Data Found", label: "No Data Found" },
];

export default function ClientPage() {
  const router = useRouter();
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [err, setErr] = useState("");
  const [importMsg, setImportMsg] = useState("");
  const [importErr, setImportErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const items = await listRequests({ q, status_filter: statusFilter });
      // The backend selects whole requests that have AT LEAST ONE number in the
      // chosen status. Trim each request down to only its matching numbers so
      // the table shows just the records for that status (works alongside the
      // Request Number search, which the backend already applies).
      const filtered = statusFilter
        ? items
            .map((r) => ({ ...r, numbers: r.numbers.filter((n) => n.status === statusFilter) }))
            .filter((r) => r.numbers.length > 0)
        : items;
      setRequests(filtered);
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [q, statusFilter]);

  useEffect(() => {
    if (!getSession()) {
      router.replace("/login");
      return;
    }
    refresh();
    const ws = requestsSocket(() => refresh());
    return () => ws?.close();
  }, [refresh, router]);

  async function onImport() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setImportErr("Choose a file first.");
      return;
    }
    setImportErr("");
    setImportMsg("");
    try {
      const res = await importRequests(file);
      setImportMsg(`Imported ${res.created} request(s), ${res.failed} failed.`);
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (e) {
      setImportErr((e as Error).message);
    }
  }

  return (
    <>
      <Topbar subtitle="CLIENT DASHBOARD" />
      <div className="container">
        <div className="card">
          <h2>Import (Excel)</h2>
          <div className="row">
            <input ref={fileRef} type="file" accept=".xlsx,.xlsm" />
            <button type="button" className="secondary" style={{ flex: "0 0 auto" }} onClick={onImport}>
              Import
            </button>
          </div>
          <p className="muted">
            Columns: Request Number, Mobile/CNIC/IMEI No, Network (Ufone / Mobilink / Telenor /
            Zong), Request Type (CDR / IMEI / Gateway), Duration Days, Case Officer, Justification
          </p>
          {importMsg && <div className="ok">{importMsg}</div>}
          {importErr && <div className="error">{importErr}</div>}
        </div>

        <div className="card">
          <h2 style={{ textAlign: "center" }}>My Requests</h2>
          {err && <div className="error">{err}</div>}
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
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <RequestsTable requests={requests} perspective="client" />
        </div>
      </div>
    </>
  );
}
