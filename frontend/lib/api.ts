// Same-origin by default: Next.js forwards /api/* to the backend (see next.config.ts).
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export type Factor = { feature: string; label: string; value: string; impact: number };

export type Appraisal = {
  id: string;
  created_at: string;
  model_version: string;
  vehicle: {
    vin: string; model_id: string; make: string; model: string; pack_kwh: number; chemistry: string;
    age_years: number; odometer_km: number; city: string; climate: string;
  };
  inputs: {
    sources: Record<string, boolean>;
    derived: Record<string, number | null>;
    service_history: { provided: boolean; method: string | null; battery_repairs: number; module_replaced: boolean; notes: string[] };
  };
  health: { soh: number; low: number; high: number };
  confidence: "high" | "medium" | "low";
  grade: { grade: "A" | "B" | "C" | "D"; label: string };
  remaining_life: { rul_years: number | null; rul_km: number | null; beyond_horizon: boolean; horizon_years: number; curve: { age: number; soh: number }[] };
  benchmark_curve: { age: number; soh: number }[];
  factors: Factor[];
  anomaly: { checked: boolean; flagged: boolean; reasons: string[] };
  valuation: {
    market_price_inr: number; market_price_source: string; expected_soh: number; delta_points: number;
    pack_replacement_inr: number; value_per_point_inr: number; battery_adjustment_inr: number; fair_price_inr: number; assumptions: string;
  };
  warranty: { active: boolean; years_left: number; km_left: number; terms: string };
  route: { code: string; title: string; action: string; notify_partners: boolean };
  co2: { kept_in_use: boolean; avoided_kg: number; basis: string };
  warnings: string[];
  summary: string;
  summary_method: string;
  links: { verify: string };
};

export type Brief = {
  id: string; created_at: string; vin: string; vehicle: string; soh: number; grade: string; route: string;
  fair_price_inr: number; adjustment_inr: number; co2_avoided_kg: number; flagged: boolean;
};

export type Sample = {
  key: string; title: string; story: string;
  form: { vin: string; model_id: string; age_years: number; odometer_km: number; city: string; market_price_lakh: number };
  dongle: Record<string, unknown>;
  invoice: { filename: string; text: string };
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new Error("Can't reach the SecondCharge API. Start the backend and try again.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    const msg = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((d: { loc?: string[]; msg: string }) => `${d.loc?.slice(-1)[0] ?? "field"}: ${d.msg}`).join("; ")
      : `Request failed (${res.status}).`;
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export function inr(v: number): string {
  const sign = v < 0 ? "-" : "";
  return `${sign}₹${Math.round(Math.abs(v)).toLocaleString("en-IN")}`;
}

export function lakh(v: number): string {
  return `₹${(v / 100000).toFixed(2)} L`;
}

export const GRADE_STYLE: Record<string, { bg: string; text: string; bar: string }> = {
  A: { bg: "bg-teal-soft", text: "text-teal", bar: "#0D7A6B" },
  B: { bg: "bg-info-soft", text: "text-info", bar: "#2C5D9E" },
  C: { bg: "bg-amber-soft", text: "text-amber", bar: "#E39B2E" },
  D: { bg: "bg-danger-soft", text: "text-danger", bar: "#C0443A" },
};
