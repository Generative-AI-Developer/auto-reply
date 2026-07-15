"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login, setSession } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const session = await login(userId.trim(), password);
      setSession(session);
      router.replace(session.role === "admin" ? "/dashboard" : "/client");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <form className="card login-card" onSubmit={onSubmit}>
        <h2>Auto-Reply — Sign in</h2>
        <div className="field">
          <label>User ID</label>
          <input value={userId} onChange={(e) => setUserId(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {error && <div className="error">{error}</div>}
      </form>
    </div>
  );
}
