"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Topbar from "@/components/Topbar";
import RequestsTable from "@/components/RequestsTable";
import {
  createRequest,
  getSession,
  importRequests,
  listRequests,
  requestsSocket,
} from "@/lib/api";
import { RequestItem } from "@/lib/types";

export default function ClientPage() {
  const router = useRouter();
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [q, setQ] = useState("");
  const [requestNumber, setRequestNumber] = useState("");
  const [numbers, setNumbers] = useState<string[]>([]);
  const [numberInput, setNumberInput] = useState("");
  const [requestType, setRequestType] = useState("");
  const [durationDays, setDurationDays] = useState("");
  const [caseOfficer, setCaseOfficer] = useState("");
  const [justification, setJustification] = useState("");
  const [msg, setMsg] = useState("");
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

  function addNumber() {
    const v = numberInput.trim();
    if (v && !numbers.includes(v)) setNumbers([...numbers, v]);
    setNumberInput("");
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setMsg("");
    if (!requestNumber.trim()) {
      setErr("Request Number is required.");
      return;
    }
    const all = [...numbers];
    if (numberInput.trim()) all.push(numberInput.trim());
    if (all.length === 0) {
      setErr("Add at least one number.");
      return;
    }
    try {
      const created = await createRequest({
        request_number: requestNumber.trim(),
        numbers: all,
        request_type: requestType,
        duration_days: durationDays ? parseInt(durationDays, 10) : null,
        case_officer: caseOfficer,
        justification,
      });
      setMsg(`Created ${created.request_id}`);
      setRequestNumber("");
      setNumbers([]);
      setNumberInput("");
      setRequestType("");
      setDurationDays("");
      setCaseOfficer("");
      setJustification("");
      refresh();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

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
      <Topbar subtitle="My Requests" />
      <div className="container">
        <div className="card">
          <h2>Bulk Import (Excel)</h2>
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

        <form className="card" onSubmit={submit}>
          <h2>New Request</h2>
          <div className="field">
            <label>Request Number</label>
            <input value={requestNumber} onChange={(e) => setRequestNumber(e.target.value)} required />
          </div>
          <div className="field">
            <label>Mobile/CNIC/IMEI No</label>
            <div className="row">
              <input
                value={numberInput}
                onChange={(e) => setNumberInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addNumber();
                  }
                }}
                placeholder="Type a number and press Add"
              />
              <button
                type="button"
                className="secondary"
                style={{ flex: "0 0 auto" }}
                onClick={addNumber}
              >
                + Add
              </button>
            </div>
            <div className="chips">
              {numbers.map((n) => (
                <span key={n} className="chip">
                  {n}
                  <button type="button" onClick={() => setNumbers(numbers.filter((x) => x !== n))}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>
          <div className="row">
            <div className="field">
              <label>Request Type</label>
              <input
                list="request-type-options"
                value={requestType}
                onChange={(e) => setRequestType(e.target.value)}
                placeholder="NIC, CDR, IPDR…"
              />
              <datalist id="request-type-options">
                <option value="NIC" />
                <option value="CDR" />
                <option value="IPDR" />
              </datalist>
            </div>
            <div className="field">
              <label>Duration (days)</label>
              <input
                type="number"
                value={durationDays}
                onChange={(e) => setDurationDays(e.target.value)}
              />
            </div>
            <div className="field">
              <label>Case Officer</label>
              <input value={caseOfficer} onChange={(e) => setCaseOfficer(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label>Justification</label>
            <textarea value={justification} onChange={(e) => setJustification(e.target.value)} />
          </div>
          <button type="submit">Submit</button>
          {msg && <div className="ok">{msg}</div>}
          {err && <div className="error">{err}</div>}
        </form>

        <div className="card">
          <h2>My Requests</h2>
          <div className="search">
            <input
              className="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="🔍 Search by Request ID or number…"
            />
          </div>
          <RequestsTable requests={requests} perspective="client" />
        </div>
      </div>
    </>
  );
}
