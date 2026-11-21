"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { FactorBars, HealthBand, ProjectionChart, SohRing } from "@/components/charts";
import { API_URL, api, Appraisal, GRADE_STYLE, inr, lakh } from "@/lib/api";

const SOURCE_LABELS: Record<string, string> = {
  diagnostics: "OBD-II / BMS read",
  charge_sessions: "Charge sessions",
  service_history: "Service invoice",
  vin_decode: "VIN decode",
};

export default function AppraisalPage() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<Appraisal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [automation, setAutomation] = useState<boolean | null>(null);

  useEffect(() => {
    api<Appraisal>(`/api/appraisals/${id}`).then(setR).catch((e: Error) => setError(e.message));
    api<{ automation: { n8n_webhook: boolean } }>("/api/health").then((h) => setAutomation(h.automation.n8n_webhook)).catch(() => setAutomation(false));
  }, [id]);

  if (error) return <p role="alert" className="card text-danger">{error}</p>;
  if (!r) return (
    <div className="grid gap-4" aria-busy="true">
      <div className="h-10 w-2/3 animate-pulse rounded bg-line/60" />
      <div className="h-52 animate-pulse rounded-2xl bg-deep/80" />
      <div className="grid gap-4 md:grid-cols-2"><div className="h-32 animate-pulse rounded-xl bg-line/50" /><div className="h-32 animate-pulse rounded-xl bg-line/50" /></div>
    </div>
  );

  const g = GRADE_STYLE[r.grade.grade];
  const v = r.vehicle;
  const life = r.remaining_life;
  const adj = r.valuation.battery_adjustment_inr;

  return (
    <div className="grid gap-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div className="grid gap-1">
          <span className="eyebrow">Appraisal {r.id}</span>
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{v.make} {v.model}</h1>
          <p className="font-mono text-sm text-muted">
            {v.vin} · {v.age_years} yrs · {v.odometer_km.toLocaleString("en-IN")} km · {v.chemistry} {v.pack_kwh} kWh · {v.city} ({v.climate})
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a className="btn-primary" href={`${API_URL}/api/appraisals/${r.id}/certificate.pdf`} target="_blank" rel="noopener">Battery certificate (PDF)</a>
          <a className="btn-ghost" href={`${API_URL}/api/appraisals/${r.id}/passport.json`} target="_blank" rel="noopener">Battery passport</a>
          <Link className="btn-ghost" href={`/verify/${r.id}`}>Verification page</Link>
        </div>
      </section>

      {r.warnings.length > 0 && (
        <div className="rounded-lg border border-amber-bright/50 bg-amber-soft px-4 py-3 text-sm text-ink">
          {r.warnings.map((w) => <p key={w}>{w}</p>)}
        </div>
      )}

      <section className="grid gap-6 rounded-2xl bg-deep p-6 text-white sm:p-8 lg:grid-cols-[auto_1fr] lg:items-center">
        <div className="flex items-center gap-5">
          <SohRing size={140} soh={r.health.soh} low={r.health.low} high={r.health.high} color={g.bar === "#0D7A6B" ? "#5CC9B4" : g.bar} />
          <div className="grid gap-2">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-mint">State of health</span>
            <span className={`w-fit whitespace-nowrap rounded-md px-2.5 py-1 font-mono text-sm font-semibold ${g.bg} ${g.text}`}>Grade {r.grade.grade} · {r.grade.label}</span>
            <span className="text-sm text-[#CFE6E1]">{r.confidence[0].toUpperCase() + r.confidence.slice(1)} confidence</span>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="grid content-start gap-1 rounded-xl bg-white/5 p-4 ring-1 ring-white/10">
            <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-teal-mint">Remaining life to 70%</span>
            <span className="font-display text-3xl font-extrabold tabular-nums">
              {life.beyond_horizon ? `${life.horizon_years}+ yrs` : life.rul_years === 0 ? "Reached" : `${life.rul_years} yrs`}
            </span>
            <span className="text-sm text-[#CFE6E1]">
              {life.beyond_horizon ? `Above 70% until at least age ${Math.round(v.age_years + life.horizon_years)}`
                : life.rul_years === 0 ? "End of first life"
                : `≈ ${life.rul_km?.toLocaleString("en-IN")} km more`}
            </span>
          </div>
          <div className="grid content-start gap-1 rounded-xl bg-white/5 p-4 ring-1 ring-white/10">
            <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-teal-mint">Fair trade-in price</span>
            <span className="font-display text-3xl font-extrabold tabular-nums">{lakh(r.valuation.fair_price_inr)}</span>
            <span className={`font-mono text-sm font-semibold ${adj >= 0 ? "text-teal-mint" : "text-[#F4A79F]"}`}>{adj >= 0 ? "+" : ""}{inr(adj)} for the battery</span>
          </div>
          <div className="grid content-start gap-1 rounded-xl bg-white/5 p-4 ring-1 ring-white/10">
            <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-teal-mint">Next life</span>
            <span className="font-display text-lg font-bold leading-snug">{r.route.title}</span>
            <span className="font-mono text-sm text-teal-mint">{r.co2.kept_in_use ? `≈ ${r.co2.avoided_kg.toLocaleString("en-IN")} kg CO2e avoided` : "Materials recovered"}</span>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="card grid content-start gap-2">
          <h2 className="text-lg font-semibold">Recommended action</h2>
          <p>{r.route.action}</p>
          <p className="text-sm text-muted">Warranty: {r.warranty.active ? `${r.warranty.years_left} ${r.warranty.years_left === 1 ? "yr" : "yrs"} / ${r.warranty.km_left.toLocaleString("en-IN")} km left` : "expired"} ({r.warranty.terms})</p>
        </div>
        <div className="card grid content-start gap-3">
          <h2 className="text-lg font-semibold">Health range</h2>
          <HealthBand soh={r.health.soh} low={r.health.low} high={r.health.high} color={g.bar} />
          <p className="text-sm text-muted">Likely {r.health.low.toFixed(1)}–{r.health.high.toFixed(1)}% · expected {r.valuation.expected_soh.toFixed(1)}% for a typical {v.make} {v.model.split(" (")[0]} this age</p>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="card grid gap-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">Health forecast</h2>
            <span className="text-xs text-muted">Model projection using this owner&apos;s km per year and charging habits</span>
          </div>
          <ProjectionChart car={life.curve} benchmark={r.benchmark_curve} currentAge={v.age_years} />
        </div>
        <div className="card grid content-start gap-4">
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">Why this score</h2>
            <span className="text-xs text-muted">SHAP, points vs fleet average</span>
          </div>
          <FactorBars factors={r.factors} />
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="card grid content-start gap-3 lg:col-span-2">
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">Summary for the seller</h2>
            <span className="rounded bg-tint px-2 py-0.5 font-mono text-[11px] text-muted">{r.summary_method === "claude" ? "written by Claude" : "template (Claude API not configured)"}</span>
          </div>
          <p className="leading-relaxed">{r.summary}</p>
          <h3 className="mt-2 text-sm font-semibold text-muted">Price breakdown</h3>
          <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-1.5 text-sm tabular-nums">
            <dt className="text-muted">Market price ({r.valuation.market_price_source})</dt><dd className="font-mono">{inr(r.valuation.market_price_inr)}</dd>
            <dt className="text-muted">Measured vs expected health</dt><dd className="font-mono">{r.health.soh.toFixed(1)}% vs {r.valuation.expected_soh.toFixed(1)}% ({r.valuation.delta_points > 0 ? "+" : ""}{r.valuation.delta_points} pts)</dd>
            <dt className="text-muted">Value per health point</dt><dd className="font-mono">{inr(r.valuation.value_per_point_inr)}</dd>
            <dt className="text-muted">Battery adjustment</dt><dd className="font-mono">{adj >= 0 ? "+" : ""}{inr(adj)}</dd>
            <dt className="font-semibold">Fair trade-in price</dt><dd className="font-mono font-semibold">{inr(r.valuation.fair_price_inr)}</dd>
          </dl>
          <p className="text-xs text-muted">{r.valuation.assumptions}</p>
        </div>
        <div className="card grid content-start gap-4">
          <div className="grid gap-2">
            <h2 className="text-lg font-semibold">Data used</h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(r.inputs.sources).map(([k, on]) => (
                <span key={k} className={`rounded-full px-2.5 py-1 text-xs font-medium ${on ? "bg-teal-soft text-teal" : "bg-tint text-muted line-through"}`}>{SOURCE_LABELS[k] ?? k}</span>
              ))}
            </div>
          </div>
          {r.anomaly.checked && (
            <div className={`rounded-md px-3 py-2 text-sm ${r.anomaly.flagged ? "bg-danger-soft text-danger" : "bg-teal-soft text-teal"}`}>
              {r.anomaly.flagged ? r.anomaly.reasons.join(". ") : "No weak modules detected."}
            </div>
          )}
          {r.inputs.service_history.provided && (
            <div className="grid gap-1 text-sm">
              <h3 className="font-semibold">Service history <span className="font-normal text-muted">({r.inputs.service_history.method === "claude" ? "read by Claude" : "rule-based reader"})</span></h3>
              <p className="text-muted">{r.inputs.service_history.battery_repairs} battery repair(s){r.inputs.service_history.module_replaced ? ", module replaced" : ""}</p>
              <ul className="list-disc pl-5 text-muted">{r.inputs.service_history.notes.slice(0, 4).map((n) => <li key={n}>{n}</li>)}</ul>
            </div>
          )}
          <div className="grid gap-1 text-sm">
            <h3 className="font-semibold">Automations</h3>
            <ul className="grid gap-1 text-muted">
              <li>✓ Certificate issued with QR verification</li>
              <li>✓ Battery passport record stored</li>
              <li>{automation ? "✓" : "○"} Seller notified{r.route.notify_partners ? " · partners alerted" : ""} {automation ? "via n8n" : "(n8n webhook not configured)"}</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}
