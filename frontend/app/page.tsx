"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSession } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const s = getSession();
    if (!s) router.replace("/login");
    else router.replace(s.role === "admin" ? "/dashboard" : "/client");
  }, [router]);
  return <div className="center muted">Loading…</div>;
}
