"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Topbar from "@/components/Topbar";
import RequestsTable from "@/components/RequestsTable";
import { getSession, importRequests, listRequests, requestsSocket } from "@/lib/api";
import { RequestItem } from "@/lib/types";

export default function ClientPage() {
  const router = useRouter();
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [importMsg, setImportMsg] = useState("");
  const [importErr, setImportErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setRequests(await listRequests({ q }));
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [q]);

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
            Columns: Request Number, Mobile/CNIC/IMEI No, Request Type, Duration Days, Case Officer,
            Justification
          </p>
          {importMsg && <div className="ok">{importMsg}</div>}
          {importErr && <div className="error">{importErr}</div>}
        </div>

        <div className="card">
          <h2 style={{ textAlign: "center" }}>My Requests</h2>
          {err && <div className="error">{err}</div>}
          <div className="search">
            <input
              className="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="🔍 Search by Request Number or Mobile/CNIC/IMEI No…"
            />
          </div>
          <RequestsTable requests={requests} perspective="client" />
        </div>
      </div>
    </>
  );
}
