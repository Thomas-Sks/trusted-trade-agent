"use client";
import { useState } from "react";
import { ApprovalsPanel } from "@/components/ApprovalsPanel";
import { AuditPanel } from "@/components/AuditPanel";
import { BuyerPanel } from "@/components/BuyerPanel";
import { RegieBar } from "@/components/RegieBar";
import type { Org } from "@/lib/api";

export default function Home() {
  const [org, setOrg] = useState<Org>("hotel");
  return (
    <main className="mx-auto flex h-screen max-w-[1600px] flex-col gap-4 p-4 lg:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-grape via-bubble to-sun text-xl text-white shadow-lg">⟁</div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight">Trusted Trade Agent Protocol</h1>
            <p className="text-xs text-muted">Achats par agents, ouverts et vérifiables · Valio Aimo × Junction 2026</p>
          </div>
        </div>
        <RegieBar />
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[1.2fr_1fr_1fr]">
        <BuyerPanel org={org} onOrg={setOrg} />
        <AuditPanel org={org} />
        <ApprovalsPanel org={org} />
      </div>
    </main>
  );
}
