import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { DashboardIcon, PackageIcon, SettingsIcon } from "@/app/components/icons";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-jetbrains-mono" });

export const metadata: Metadata = {
  title: "Order Supervisor",
  description: "Order Supervisor System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="min-h-screen bg-surface text-on-surface font-sans antialiased">
        <header className="fixed top-0 left-0 w-full z-50 flex items-center px-6 h-16 bg-surface-bright border-b border-outline-variant">
          <Link href="/runs" className="flex items-center gap-2">
            <PackageIcon className="w-5 h-5 text-on-surface" />
            <span className="text-base font-semibold text-on-surface">Order Supervisor</span>
          </Link>
        </header>

        <aside className="hidden lg:flex flex-col h-full w-56 fixed left-0 top-16 py-6 bg-surface-container-low border-r border-outline-variant z-40">
          <nav className="flex flex-col px-3 gap-1">
            <NavItem href="/runs" icon={<DashboardIcon className="w-5 h-5" />} label="Runs" />
            <NavItem href="/supervisors" icon={<SettingsIcon className="w-5 h-5" />} label="Supervisor Configs" />
          </nav>
        </aside>

        <main className="lg:ml-56 pt-24 pb-12 px-6 min-h-screen">
          <div className="max-w-[1200px] mx-auto">{children}</div>
        </main>
      </body>
    </html>
  );
}

function NavItem({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-3 py-2 text-on-surface-variant hover:bg-outline-variant/40 transition-colors rounded text-sm font-medium"
    >
      {icon}
      {label}
    </Link>
  );
}
