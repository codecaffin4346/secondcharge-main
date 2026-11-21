"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, Appraisal, Sample } from "@/lib/api";

type Models = { models: { model_id: string; make: string; model: string; pack_kwh: number; chemistry: string }[]; cities: string[] };
type Health = { model_metrics: { soh_mae_points?: number; band_80pct_coverage?: number; training_vehicles?: number }; llm: { enabled: boolean } };

const EMPTY = { vin: "", model_id: "", age_years: "", odometer_km: "", city: "", market_price_lakh: "", seller_contact: "" };
const SAMPLE_HINT: Record<string, { grade: string; tone: string }> = {
  "careful-owner": { grade: "Expect A", tone: "bg-teal-soft text-teal" },
  "fast-charged-heat": { grade: "Expect C", tone: "bg-amber-soft text-amber" },
  "fleet-weak-module": { grade: "Expect D", tone: "bg-danger-soft text-danger" },
};
const FLOW = [
  ["Capture", "VIN, odometer, OBD-II read, invoice"],
  ["Predict", "Health with a range, remaining life"],
  ["Decide", "Fair price and the battery's next life"],
  ["Act", "Certificate, passport, partner alerts"],
];
const STEPS = ["Reading diagnostic data…", "Extracting service history…", "Estimating state of health…", "Forecasting remaining life…", "Pricing and routing…", "Writing the summary…"];

export default function AppraisePage() {
  const router = useRouter();
  const [meta, setMeta] = useState<Models | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [dongle, setDongle] = useState("");
  const [invoice, setInvoice] = useState<File | null>(null);
  const [activeSample, setActiveSample] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    Promise.all([api<Models>("/api/vehicle-models"), api<{ samples: Sample[] }>("/api/samples")])
      .then(([m, s]) => {
        setMeta(m);
        setSamples(s.samples);
        if (s.samples[0]) loadSample(s.samples[0]);
      })
      .catch((e: Error) => setError(e.message));
    api<Health>("/api/health").then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 700);
    return () => clearInterval(t);
  }, [busy]);

  const dongleSummary = useMemo(() => {
    if (!dongle.trim()) return null;
    try {
      const d = JSON.parse(dongle);
      const sessions = Array.isArray(d.charge_sessions) ? d.charge_sessions : [];
      const dc = sessions.filter((s: { dc?: boolean }) => s.dc).length;
      const cells: number[] = Array.isArray(d.cell_voltages_mv) ? d.cell_voltages_mv : [];
      return {
        ok: true as const,
        items: [
          ["Cells read", cells.length ? `${cells.length}` : "–"],
          ["Cell spread", cells.length > 1 ? `${Math.max(...cells) - Math.min(...cells)} mV` : "–"],
          ["Charge sessions", sessions.length ? `${sessions.length} (${Math.round((dc / sessions.length) * 100)}% DC)` : "–"],
          ["BMS health", d.bms_soh_pct != null ? `${d.bms_soh_pct}%` : "–"],
        ],
        reader: d.reader as string | undefined,
      };
    } catch {
      return { ok: false as const };
    }
  }, [dongle]);

  function loadSample(s: Sample) {
    setActiveSample(s.key);
    setForm({
      vin: s.form.vin, model_id: s.form.model_id, age_years: String(s.form.age_years), odometer_km: String(s.form.odometer_km),
      city: s.form.city, market_price_lakh: String(s.form.market_price_lakh), seller_contact: "seller@example.com",
    });
    setDongle(JSON.stringify(s.dongle, null, 2));
    setInvoice(new File([s.invoice.text], s.invoice.filename, { type: "text/plain" }));
    setError(null);
  }

  function set<K extends keyof typeof EMPTY>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
    setActiveSample(null);
  }

  async function onVinBlur() {
    if (form.vin.length < 11 || form.model_id) return;
    try {
      const r = await api<{ candidates: string[] }>(`/api/vin/${encodeURIComponent(form.vin)}`);
      if (r.candidates.length) setForm((f) => ({ ...f, model_id: r.candidates[0] }));
    } catch { /* decoding is a convenience only */ }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStep(0);
    setError(null);
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => { if (v !== "") fd.append(k, v); });
    if (dongle.trim()) fd.append("dongle_json", dongle);
    if (invoice) fd.append("invoice_file", invoice);
    try {
      const r = await api<Appraisal>("/api/appraisals", { method: "POST", body: fd });
      router.push(`/appraisals/${r.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const m = health?.model_metrics;

  return (
    <div className="grid gap-8">
      <section className="relative overflow-hidden rounded-2xl bg-deep px-6 py-8 text-white sm:px-10 sm:py-10">
        <div aria-hidden className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full border-[28px] border-teal/40" />
        <div aria-hidden className="pointer-events-none absolute -right-2 top-20 h-40 w-40 rounded-full border-[16px] border-teal-mint/20" />
        <div className="relative grid max-w-3xl gap-4">
          <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-mint">EV trade-in battery appraisal</span>
          <h1 className="text-3xl font-extrabold leading-tight tracking-tight sm:text-5xl">Price the battery, not the odometer</h1>
          <p className="max-w-2xl text-base text-[#CFE6E1] sm:text-lg">
            Measure a used EV&apos;s battery health in under a minute, pay sellers fairly for well-kept packs, and send every battery to its best next life.
          </p>
          <div className="flex flex-wrap gap-2 pt-1 font-mono text-xs">
            {m?.soh_mae_points != null && <span className="rounded-full bg-white/10 px-3 py-1">±{m.soh_mae_points} pt average error</span>}
            {m?.band_80pct_coverage != null && <span className="rounded-full bg-white/10 px-3 py-1">80% range covers {(m.band_80pct_coverage * 100).toFixed(0)}% of cars</span>}
            {m?.training_vehicles != null && <span className="rounded-full bg-white/10 px-3 py-1">trained on {m.training_vehicles.toLocaleString("en-IN")} synthetic EVs</span>}
            {health && <span className="rounded-full bg-white/10 px-3 py-1">{health.llm.enabled ? "Claude summaries on" : "offline summaries"}</span>}
          </div>
        </div>
        <ol className="relative mt-8 grid gap-3 sm:grid-cols-4">
          {FLOW.map(([t, d], i) => (
            <li key={t} className="grid gap-1 rounded-xl bg-white/5 p-3 ring-1 ring-white/10">
              <span className="font-mono text-xs text-teal-mint">{i + 1} · {t}</span>
              <span className="text-sm text-[#CFE6E1]">{d}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="grid gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xl font-bold">Start with a demo car</h2>
          <span className="text-sm text-muted">Each one fills the form with its diagnostic read and service invoice</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {samples.map((s) => {
            const active = activeSample === s.key;
            const hint = SAMPLE_HINT[s.key];
            return (
              <button key={s.key} type="button" onClick={() => loadSample(s)} aria-pressed={active}
                className={`card grid gap-2 text-left transition hover:-translate-y-0.5 hover:border-teal hover:shadow-md ${active ? "border-teal shadow-md ring-2 ring-teal/25" : ""}`}>
                <span className="flex items-center justify-between gap-2">
                  <span className="font-display text-lg font-semibold">{s.title}</span>
                  {hint && <span className={`rounded-full px-2 py-0.5 font-mono text-[11px] font-semibold ${hint.tone}`}>{hint.grade}</span>}
                </span>
                <span className="text-sm text-muted">{s.story}</span>
                <span className="font-mono text-xs text-muted">{s.form.city} · {s.form.age_years} yrs · {s.form.odometer_km.toLocaleString("en-IN")} km</span>
                <span className={`text-sm font-semibold ${active ? "text-teal" : "text-muted"}`}>{active ? "✓ Loaded" : "Load this car →"}</span>
              </button>
            );
          })}
        </div>
      </section>

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="card grid content-start gap-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold"><StepDot n={1} /> Vehicle</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="vin">VIN</label>
              <input id="vin" className="input font-mono uppercase tracking-wider" required minLength={11} maxLength={17} value={form.vin}
                onChange={(e) => set("vin", e.target.value.toUpperCase())} onBlur={onVinBlur} placeholder="17-character VIN" />
            </div>
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="model_id">Model</label>
              <select id="model_id" className="input" required value={form.model_id} onChange={(e) => set("model_id", e.target.value)}>
                <option value="">Choose a model</option>
                {meta?.models.map((md) => (
                  <option key={md.model_id} value={md.model_id}>{md.make} {md.model} · {md.chemistry}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="age_years">Age (years)</label>
              <input id="age_years" className="input" type="number" step="0.1" min="0.1" max="20" required value={form.age_years} onChange={(e) => set("age_years", e.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="odometer_km">Odometer (km)</label>
              <input id="odometer_km" className="input" type="number" min="0" required value={form.odometer_km} onChange={(e) => set("odometer_km", e.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="city">City</label>
              <select id="city" className="input" required value={form.city} onChange={(e) => set("city", e.target.value)}>
                <option value="">Choose a city</option>
                {meta?.cities.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="market_price_lakh">Market price (₹ lakh)</label>
              <input id="market_price_lakh" className="input" type="number" step="0.1" min="0.1" value={form.market_price_lakh} onChange={(e) => set("market_price_lakh", e.target.value)} placeholder="Estimated if blank" />
            </div>
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="seller_contact">Seller email or phone</label>
              <input id="seller_contact" className="input" value={form.seller_contact} onChange={(e) => set("seller_contact", e.target.value)} placeholder="Where the certificate is sent" />
            </div>
          </div>
        </div>

        <div className="card grid content-start gap-5">
          <h2 className="flex items-center gap-2 text-lg font-semibold"><StepDot n={2} /> Diagnostic and service data</h2>

          <div className="grid gap-2">
            <span className="field-label mb-0">OBD-II / BMS read</span>
            {dongleSummary?.ok ? (
              <div className="grid gap-3 rounded-lg bg-tint p-3">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-semibold text-teal">✓ Diagnostic data loaded</span>
                  {dongleSummary.reader && <span className="font-mono text-xs text-muted">{dongleSummary.reader}</span>}
                </div>
                <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {dongleSummary.items.map(([k, v]) => (
                    <div key={k} className="rounded-md bg-white px-2.5 py-2">
                      <dt className="text-[11px] text-muted">{k}</dt>
                      <dd className="font-mono text-sm font-semibold">{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : dongleSummary && !dongleSummary.ok ? (
              <p className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">This isn&apos;t valid JSON yet. Fix it below or load a demo car.</p>
            ) : (
              <p className="rounded-md bg-tint px-3 py-2 text-sm text-muted">No diagnostic read. The estimate will use history only, with a wider range.</p>
            )}
            <details className="group text-sm">
              <summary className="cursor-pointer select-none text-muted hover:text-ink">Edit raw JSON</summary>
              <textarea id="dongle" aria-label="Diagnostic data JSON" className="input mt-2 h-48 font-mono text-xs" value={dongle}
                onChange={(e) => { setDongle(e.target.value); setActiveSample(null); }} spellCheck={false}
                placeholder='{"cell_voltages_mv": [...], "charge_sessions": [...]}' />
            </details>
          </div>

          <div className="grid gap-2">
            <span className="field-label mb-0">Service invoice</span>
            <label htmlFor="invoice"
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f) { setInvoice(f); setActiveSample(null); } }}
              className={`flex cursor-pointer items-center justify-between gap-3 rounded-lg border-2 border-dashed px-4 py-3 text-sm transition ${dragging ? "border-teal bg-teal-soft" : "border-line hover:border-teal hover:bg-tint"}`}>
              <span className="grid">
                <span className="font-medium">{invoice ? invoice.name : "Drop a PDF or text invoice here"}</span>
                <span className="text-xs text-muted">{invoice ? "Battery repairs and module swaps are read from it" : "or click to choose a file"}</span>
              </span>
              <span className="rounded-md bg-white px-2.5 py-1 text-xs font-semibold text-teal ring-1 ring-line">{invoice ? "Replace" : "Choose file"}</span>
            </label>
            <input id="invoice" type="file" accept=".pdf,.txt,.csv" className="sr-only"
              onChange={(e) => { const f = e.target.files?.[0] ?? null; setInvoice(f); setActiveSample(null); }} />
          </div>

          {error && <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
          <button className="btn-primary h-12 text-base shadow-sm" disabled={busy || !meta}>
            {busy ? (
              <span className="flex items-center gap-2"><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />{STEPS[step]}</span>
            ) : "Appraise battery →"}
          </button>
        </div>
      </form>
    </div>
  );
}

function StepDot({ n }: { n: number }) {
  return <span className="grid h-7 w-7 place-items-center rounded-full bg-teal font-mono text-sm text-white">{n}</span>;
}
