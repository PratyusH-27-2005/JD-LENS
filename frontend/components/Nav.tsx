"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/new", label: "Paste posting" },
  { href: "/profile", label: "Profile" },
];

export function Nav() {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" || path.startsWith("/postings") : path === href);

  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight text-stone-900">
          <span aria-hidden className="grid size-7 place-items-center rounded-md bg-stone-900 text-xs text-amber-300">
            JD
          </span>
          JD Lens
        </Link>
        <nav className="flex gap-1 text-sm">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={active(l.href) ? "page" : undefined}
              className={`rounded-md px-3 py-1.5 transition-colors ${
                active(l.href) ? "bg-stone-100 font-medium text-stone-900" : "text-stone-600 hover:text-stone-900"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
