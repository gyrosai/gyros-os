import type { Metadata } from "next";
import type { CSSProperties } from "react";
import { Plus_Jakarta_Sans, Inter, Geist_Mono } from "next/font/google";
import { AppShell } from "@/components/app-shell";
import { studioConfig } from "@/lib/runtime-config";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
});

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const brandFont = studioConfig.name.toLowerCase().includes("gyros")
  ? jakarta
  : inter;

export const metadata: Metadata = {
  title: studioConfig.name,
  description: `${studioConfig.name} — assistente IA`,
};

function buildBrandStyle(): CSSProperties {
  const { brand } = studioConfig;
  const solid = brand.kind === "solid" ? brand.color : brand.to;
  const gradient =
    brand.kind === "gradient"
      ? `linear-gradient(${brand.angle}, ${brand.from}, ${brand.to})`
      : "none";
  return {
    ["--brand-solid" as string]: solid,
    ["--brand-gradient" as string]: gradient,
  } as CSSProperties;
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" style={buildBrandStyle()}>
      <body
        className={`${brandFont.variable} ${geistMono.variable} antialiased`}
      >
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
