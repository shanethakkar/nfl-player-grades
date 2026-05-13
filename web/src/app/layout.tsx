import type { Metadata } from "next";
import localFont from "next/font/local";
import "@/styles/globals.css";
import { SiteHeader } from "@/components/SiteHeader";

const geistSans = localFont({
  src: "../fonts/GeistSans.woff2",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "../fonts/GeistMono.woff2",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "NFL Player Grades",
  description:
    "Every NFL player graded 0-100 using advanced stats. Browse depth charts and season/career grades for all 32 teams.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} min-h-screen font-sans antialiased`}>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
