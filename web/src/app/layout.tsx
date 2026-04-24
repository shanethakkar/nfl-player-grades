import type { Metadata } from "next";
import "@/styles/globals.css";
import { SiteHeader } from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: "NFL Player Grades",
  description:
    "Every NFL player graded 0-100 using advanced stats. Browse depth charts and season/career grades for all 32 teams.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
