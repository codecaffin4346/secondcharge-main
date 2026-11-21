"use client";

import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Factor } from "@/lib/api";

type Pt = { age: number; soh: number };

export function ProjectionChart({ car, benchmark, currentAge }: { car: Pt[]; benchmark: Pt[]; currentAge: number }) {
  const byAge = new Map<number, { age: number; car?: number; typical?: number }>();
  car.forEach((p) => byAge.set(p.age, { ...(byAge.get(p.age) ?? { age: p.age }), car: p.soh }));
  benchmark.forEach((p) => byAge.set(p.age, { ...(byAge.get(p.age) ?? { age: p.age }), typical: p.soh }));
  const data = [...byAge.values()].sort((a, b) => a.age - b.age);
  const min = Math.max(0, Math.floor(Math.min(60, ...car.map((p) => p.soh), ...benchmark.map((p) => p.soh)) / 10) * 10);
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
          <CartesianGrid stroke="#E3EBE8" vertical={false} />
          <XAxis dataKey="age" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => `${Math.round(v)}y`} tick={{ fill: "#5B6965", fontSize: 12 }} />
          <YAxis domain={[min, 100]} tickFormatter={(v) => `${v}%`} tick={{ fill: "#5B6965", fontSize: 12 }} />
          <Tooltip formatter={(v: number, n: string) => [`${v.toFixed(1)}%`, n]} labelFormatter={(v: number) => `Age ${v.toFixed(1)} years`} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={70} stroke="#C0443A" strokeDasharray="4 4" label={{ value: "End of first life (70%)", fill: "#C0443A", fontSize: 11, position: "insideBottomRight" }} />
          <ReferenceLine x={currentAge} stroke="#5B6965" strokeDasharray="2 4" label={{ value: "today", fill: "#5B6965", fontSize: 11, position: "insideTopLeft" }} />
          <Line type="monotone" dataKey="typical" name="Typical car, same model" stroke="#9AABA6" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
          <Line type="monotone" dataKey="car" name="This car (forecast)" stroke="#0D7A6B" strokeWidth={3} dot={false} connectNulls isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function FactorBars({ factors }: { factors: Factor[] }) {
  const max = Math.max(1, ...factors.map((f) => Math.abs(f.impact)));
  return (
    <ul className="grid gap-3">
      {factors.map((f) => {
        const pct = (Math.abs(f.impact) / max) * 50;
        const pos = f.impact >= 0;
        return (
          <li key={f.feature} className="grid gap-1">
            <div className="flex justify-between gap-3 text-sm">
              <span><span className="font-medium">{f.label}</span> <span className="text-muted">· {f.value}</span></span>
              <span className={`font-mono font-semibold tabular-nums ${pos ? "text-teal" : "text-danger"}`}>{pos ? "+" : ""}{f.impact.toFixed(1)} pts</span>
            </div>
            <div className="relative h-2 rounded bg-tint" aria-hidden>
              <span className="absolute left-1/2 top-[-2px] h-3 w-px bg-muted/50" />
              <span className={`absolute top-0 h-2 rounded ${pos ? "bg-teal" : "bg-danger"}`}
                style={pos ? { left: "50%", width: `${pct}%` } : { right: "50%", width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function HealthBand({ soh, low, high, color }: { soh: number; low: number; high: number; color: string }) {
  const lo = 50;
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - lo) / (100 - lo)) * 100))}%`;
  return (
    <div className="grid gap-1">
      <div className="relative h-3 rounded-full bg-tint">
        <span className="absolute top-0 h-3 rounded-full opacity-35" style={{ left: pos(low), width: `calc(${pos(high)} - ${pos(low)})`, background: color }} />
        <span className="absolute top-[-3px] h-[18px] w-[4px] -translate-x-1/2 rounded" style={{ left: pos(soh), background: color }} />
        <span className="absolute top-[-3px] h-[18px] w-px bg-danger" style={{ left: pos(70) }} />
      </div>
      <div className="relative h-4 font-mono text-[11px] text-muted">
        {[50, 70, 85, 100].map((t) => (
          <span key={t} className="absolute -translate-x-1/2 first:translate-x-0 last:-translate-x-full" style={{ left: pos(t) }}>{t}%</span>
        ))}
      </div>
    </div>
  );
}

export function SohRing({ soh, low, high, color, size = 168 }: { soh: number; low: number; high: number; color: string; size?: number }) {
  const r = 42;
  const c = 2 * Math.PI * r;
  const arc = 0.75; // 270° gauge
  const frac = (v: number) => Math.max(0, Math.min(1, v / 100));
  const dash = (v: number) => `${c * arc * frac(v)} ${c}`;
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={`State of health ${soh.toFixed(1)} percent, likely ${low.toFixed(1)} to ${high.toFixed(1)}`}>
      <g transform="rotate(135 50 50)">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.14)" strokeWidth="8" strokeDasharray={`${c * arc} ${c}`} strokeLinecap="round" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeOpacity="0.35" strokeWidth="8" strokeDasharray={dash(high)} strokeLinecap="round" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="8" strokeDasharray={dash(soh)} strokeLinecap="round" />
      </g>
      <text x="50" y="50" textAnchor="middle" fill="#FFFFFF" fontSize="17" fontWeight="800" fontFamily="var(--font-display)">{soh.toFixed(1)}%</text>
      <text x="50" y="63" textAnchor="middle" fill="#A9D9CF" fontSize="6.5" fontFamily="var(--font-mono)">{low.toFixed(0)}–{high.toFixed(0)}% range</text>
    </svg>
  );
}
