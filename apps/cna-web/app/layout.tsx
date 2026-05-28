import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CNA Platform — CBTS",
  description:
    "CBTS Cloud Network Assessment — multi-user assessment, analysis, and delivery platform",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        <meta name="color-scheme" content="light dark" />
      </head>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
