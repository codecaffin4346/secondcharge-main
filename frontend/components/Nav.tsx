"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "New appraisal", short: "Appraise", match: (p: string) => p === "/" || p.startsWith("/appraisals") },
  { href: "/dashboard", label: "Dealer dashboard", short: "Dashboard", match: (p: string) => p.startsWith("/dashboard") },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="flex gap-1 text-sm" aria-label="Main">
      {LINKS.map((l) => {
        const active = l.match(path);
        return (
          <Link key={l.href} href={l.href} aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 transition ${active ? "bg-teal-soft font-semibold text-teal" : "text-muted hover:bg-tint hover:text-ink"}`}>
            <span className="sm:hidden">{l.short}</span>
            <span className="hidden sm:inline">{l.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
