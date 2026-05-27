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
    "Every NFL player on a 0-100 scale. 2,600+ players, 189 metrics audited, every weight derived from data.",
  openGraph: {
    title: "NFL Player Grades",
    description:
      "Every NFL player on a 0-100 scale. 2,600+ players, 189 metrics audited, every weight derived from data.",
    images: [
      {
        url: "/api/og/rushmore",
        width: 1200,
        height: 630,
        alt: "NFL Player Grades — top QBs of the current season",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "NFL Player Grades",
    description:
      "Every NFL player graded 0-100. 2,600+ players, 189 metrics audited.",
    images: ["/api/og/rushmore"],
  },
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
