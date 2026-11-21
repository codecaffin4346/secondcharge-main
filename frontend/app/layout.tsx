import type { Metadata } from "next";
import { Archivo, IBM_Plex_Sans, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import Nav from "@/components/Nav";
import "./globals.css";

const display = Archivo({ subsets: ["latin"], weight: ["600", "800"], variable: "--font-display" });
const body = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-body" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "SecondCharge",
  description: "EV trade-in battery health estimator: state of health, remaining life, fair price and the battery's next life.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${body.variable} ${mono.variable}`}>
        <header className="sticky top-0 z-20 border-b border-line bg-white/90 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/" className="flex items-center gap-2">
              <span aria-hidden className="relative inline-block h-5 w-9 rounded-[4px] border-2 border-ink p-[2px] after:absolute after:-right-[5px] after:top-[4px] after:h-[7px] after:w-[3px] after:rounded-r after:bg-ink">
                <span className="block h-full w-3/4 rounded-[2px] bg-teal" />
              </span>
              <span className="font-display text-lg font-extrabold tracking-tight">SecondCharge</span>
            </Link>
            <Nav />
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-10 text-xs text-muted">
          Prototype by Team Aura++ for the Tek Qubit hackathon. Estimates come from models trained on a synthetic fleet.
        </footer>
      </body>
    </html>
  );
}
