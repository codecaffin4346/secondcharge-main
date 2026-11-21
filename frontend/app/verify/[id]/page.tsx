"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { API_URL, api, Appraisal, GRADE_STYLE } from "@/lib/api";

export default function VerifyPage() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<Appraisal | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<Appraisal>(`/api/appraisals/${id}`).then(setR).catch((e: Error) => setError(e.message)); }, [id]);

  if (error) {
    return (
      <div className="card mx-auto grid max-w-lg gap-2">
        <span className="eyebrow text-danger">Not verified</span>
        <h1 className="text-2xl font-bold">No certificate with ID {id}</h1>
        <p className="text-muted">Check the ID on the certificate. If it was printed recently, ask the dealer to re-issue it.</p>
      </div>
    );
  }
  if (!r) return <p className="text-muted">Checking certificate…</p>;
  const g = GRADE_STYLE[r.grade.grade];
  return (
    <div className="card mx-auto grid max-w-lg gap-4">
      <span className="eyebrow">Verified battery health certificate</span>
      <h1 className="text-2xl font-bold">{r.vehicle.make} {r.vehicle.model}</h1>
      <p className="font-mono text-sm text-muted">VIN {r.vehicle.vin} · issued {new Date(r.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}</p>
      <div className="flex items-baseline gap-3">
        <span className="font-display text-5xl font-extrabold tabular-nums">{r.health.soh.toFixed(1)}%</span>
        <span className={`rounded-md px-2 py-1 font-mono text-sm font-semibold ${g.bg} ${g.text}`}>Grade {r.grade.grade}</span>
      </div>
      <p className="text-sm text-muted">State of health, likely {r.health.low.toFixed(1)}–{r.health.high.toFixed(1)}%. Odometer at appraisal {r.vehicle.odometer_km.toLocaleString("en-IN")} km.</p>
      <a className="btn-ghost w-fit" href={`${API_URL}/api/appraisals/${r.id}/certificate.pdf`} target="_blank" rel="noopener">View full certificate</a>
    </div>
  );
}
