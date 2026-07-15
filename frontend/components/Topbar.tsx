"use client";

import { useRouter } from "next/navigation";
import { clearSession, getSession } from "@/lib/api";

export default function Topbar({ subtitle }: { subtitle: string }) {
  const router = useRouter();
  const session = getSession();

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
        {session?.user_id} ({session?.role}){" "}
        <button className="secondary small" onClick={logout}>
          Sign out
        </button>
      </div>
    </div>
  );
}
