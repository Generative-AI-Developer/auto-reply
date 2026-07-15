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
  const [numbers, setNumbers] = useState<string[]>([]);
  const [numberInput, setNumberInput] = useState("");
  const [durationDays, setDurationDays] = useState("");
  const [caseOfficer, setCaseOfficer] = useState("");
  const [justification, setJustification] = useState("");
  const [requestDate, setRequestDate] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
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
    const all = [...numbers];
    if (numberInput.trim()) all.push(numberInput.trim());
    if (all.length === 0) {
      setErr("Add at least one number.");
      return;
    }
    try {
      const created = await createRequest({
        numbers: all,
        duration_days: durationDays ? parseInt(durationDays, 10) : null,
        case_officer: caseOfficer,
        justification,
        request_date: requestDate || null,
      });
      setMsg(`Created ${created.request_id}`);
      setNumbers([]);
      setNumberInput("");
      setDurationDays("");
      setCaseOfficer("");
      setJustification("");
      setRequestDate("");
      refresh();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function onImport() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setErr("");
    setMsg("");
    try {
      const res = await importRequests(file);
      setMsg(`Imported ${res.created} request(s), ${res.failed} failed.`);
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (e) {
      setErr((e as Error).message);
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
            <button className="secondary" style={{ flex: "0 0 auto" }} onClick={onImport}>
              Import
            </button>
          </div>
          <p className="muted">Columns: Numbers, Duration Days, Case Officer, Justification, Request Date</p>
        </div>

        <form className="card" onSubmit={submit}>
          <h2>New Request</h2>
          <div className="field">
            <label>Numbers (Mobile / NIC / other)</label>
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
            <div className="field">
              <label>Request Date</label>
              <input type="date" value={requestDate} onChange={(e) => setRequestDate(e.target.value)} />
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
          <RequestsTable requests={requests} />
        </div>
      </div>
    </>
  );
}
