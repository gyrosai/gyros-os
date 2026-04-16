import type { Metadata } from "next";
import type { CSSProperties } from "react";
import { AppShell } from "@/components/app-shell";
import { studioConfig } from "@/lib/runtime-config";
import "./globals.css";

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
      <body className="antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
