"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Brief, GRADE_STYLE, inr, lakh } from "@/lib/api";

type Dash = {
  appraisals: number; co2_avoided_kg: number; avg_soh: number | null; seller_uplift_inr: number; flagged: number;
  grades: Record<string, number>; routes: Record<string, number>; recent: Brief[];
};

export default function Dashboard() {
  const [d, setD] = useState<Dash | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<Dash>("/api/dashboard").then(setD).catch((e: Error) => setError(e.message)); }, []);

  if (error) return <p role="alert" className="card text-danger">{error}</p>;
  if (!d) return <p className="text-muted">Loading dashboard…</p>;

  const total = Math.max(1, d.appraisals);
  return (
    <div className="grid gap-6">
      <section className="grid gap-1">
        <span className="eyebrow">Dealer dashboard</span>
        <h1 className="text-3xl font-extrabold tracking-tight">Battery appraisals and impact</h1>
      </section>

      {d.appraisals === 0 ? (
        <div className="card grid gap-2">
          <h2 className="text-lg font-semibold">No appraisals yet</h2>
          <p className="text-muted">Appraise a car to see grades, routing and CO2 impact here.</p>
          <Link href="/" className="btn-primary w-fit">Start an appraisal</Link>
        </div>
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Appraisals" value={d.appraisals.toString()} note={`${d.flagged} flagged for inspection`} />
            <Stat label="CO2e avoided" value={`${(d.co2_avoided_kg / 1000).toFixed(1)} t`} note="Packs kept in use instead of new ones built" accent />
            <Stat label="Average health" value={`${d.avg_soh?.toFixed(1)}%`} note="Across appraised batteries" />
            <Stat label="Paid to careful owners" value={inr(d.seller_uplift_inr)} note="Positive battery adjustments" />
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="card grid gap-3">
              <h2 className="text-lg font-semibold">Grades</h2>
              {(["A", "B", "C", "D"] as const).map((k) => (
                <div key={k} className="grid grid-cols-[3rem_1fr_2rem] items-center gap-3 text-sm">
                  <span className={`rounded px-2 py-0.5 text-center font-mono font-semibold ${GRADE_STYLE[k].bg} ${GRADE_STYLE[k].text}`}>{k}</span>
                  <div className="h-3 rounded bg-tint"><div className="h-3 rounded" style={{ width: `${(d.grades[k] / total) * 100}%`, background: GRADE_STYLE[k].bar }} /></div>
                  <span className="text-right font-mono tabular-nums">{d.grades[k]}</span>
                </div>
              ))}
            </div>
            <div className="card grid content-start gap-3">
              <h2 className="text-lg font-semibold">Where the batteries go next</h2>
              <ul className="grid gap-2 text-sm">
                {Object.entries(d.routes).sort((a, b) => b[1] - a[1]).map(([k, n]) => (
                  <li key={k} className="flex justify-between gap-3"><span>{k}</span><span className="font-mono tabular-nums">{n}</span></li>
                ))}
              </ul>
            </div>
          </section>

          <section className="card overflow-x-auto p-0">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-tint text-left font-mono text-[11px] uppercase tracking-wider text-muted">
                <tr><th className="px-4 py-2">Vehicle</th><th className="px-4 py-2">Health</th><th className="px-4 py-2">Next life</th><th className="px-4 py-2 text-right">Adjustment</th><th className="px-4 py-2 text-right">Fair price</th><th className="px-4 py-2 text-right">CO2e</th></tr>
              </thead>
              <tbody>
                {d.recent.map((r) => (
                  <tr key={r.id} className="border-t border-line hover:bg-tint/50">
                    <td className="px-4 py-2"><Link href={`/appraisals/${r.id}`} className="font-medium text-teal hover:underline">{r.vehicle}</Link><div className="font-mono text-xs text-muted">{r.vin}</div></td>
                    <td className="px-4 py-2"><span className={`mr-2 rounded px-1.5 py-0.5 font-mono text-xs font-semibold ${GRADE_STYLE[r.grade].bg} ${GRADE_STYLE[r.grade].text}`}>{r.grade}</span><span className="tabular-nums">{r.soh.toFixed(1)}%</span>{r.flagged && <span className="ml-2 text-xs text-danger">flagged</span>}</td>
                    <td className="px-4 py-2">{r.route}</td>
                    <td className={`px-4 py-2 text-right font-mono tabular-nums ${r.adjustment_inr >= 0 ? "text-teal" : "text-danger"}`}>{r.adjustment_inr >= 0 ? "+" : ""}{inr(r.adjustment_inr)}</td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums">{lakh(r.fair_price_inr)}</td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums">{r.co2_avoided_kg.toLocaleString("en-IN")} kg</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, note, accent }: { label: string; value: string; note: string; accent?: boolean }) {
  return (
    <div className={`card grid gap-1 ${accent ? "border-teal bg-teal text-white" : ""}`}>
      <span className={`font-mono text-[11px] font-semibold uppercase tracking-[0.12em] ${accent ? "text-teal-soft" : "text-muted"}`}>{label}</span>
      <span className="font-display text-3xl font-extrabold tabular-nums">{value}</span>
      <span className={`text-sm ${accent ? "text-teal-soft" : "text-muted"}`}>{note}</span>
    </div>
  );
}
