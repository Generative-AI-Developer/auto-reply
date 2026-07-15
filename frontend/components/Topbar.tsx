"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearSession, getSession } from "@/lib/api";
import type { Session } from "@/lib/types";

export default function Topbar({ subtitle }: { subtitle: string }) {
  const router = useRouter();
  // Session lives in localStorage, which doesn't exist during server render.
  // Reading it directly in the render body would make the server-rendered
  // HTML ("(", ")") mismatch the client's first render (real user_id/role),
  // triggering a hydration error. Deferring to an effect keeps the first
  // client render identical to the server render; the real value fills in
  // right after mount.
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    setSession(getSession());
  }, []);

  function logout() {
    clearSession();
    router.replace("/login");
  }

  return (
    <div className="topbar">
      <h1>
        Auto-Reply <span className="muted">— {subtitle}</span>
      </h1>
      <div className="muted">
        {session ? `${session.user_id} (${session.role})` : ""}{" "}
        <button className="secondary small" onClick={logout}>
          Sign out
        </button>
      </div>
    </div>
  );
}
