import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Order Supervisor",
  description: "Order Supervisor System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <nav className="border-b bg-white px-6 py-3 flex gap-6">
          <Link href="/runs" className="font-semibold">
            Order Supervisor
          </Link>
          <Link href="/runs" className="text-sm text-gray-600 hover:text-gray-900">
            Runs
          </Link>
          <Link href="/supervisors" className="text-sm text-gray-600 hover:text-gray-900">
            Supervisors
          </Link>
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
