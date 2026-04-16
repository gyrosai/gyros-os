const MIN_PRODUCTION_SECRET_LENGTH = 32;

function normalize(value: string | undefined): string {
  return (value || "").trim();
}

export function isProductionEnvironment(): boolean {
  const candidates = [
    process.env.ENVIRONMENT,
    process.env.RAILWAY_ENVIRONMENT,
    process.env.RAILWAY_ENVIRONMENT_NAME,
  ];

  return candidates.some(
    (value) => normalize(value).toLowerCase() === "production"
  );
}

function isMissing(value: string | undefined): boolean {
  return normalize(value) === "";
}

function isTooShortForProduction(value: string | undefined): boolean {
  return normalize(value).length < MIN_PRODUCTION_SECRET_LENGTH;
}

export function ensureFrontendRuntimeConfig(): void {
  const missing: string[] = [];

  if (isMissing(process.env.INTERNAL_SERVICE_TOKEN)) {
    missing.push("INTERNAL_SERVICE_TOKEN");
  }

  if (isMissing(process.env.BETTER_AUTH_SECRET)) {
    missing.push("BETTER_AUTH_SECRET");
  }

  if (missing.length > 0) {
    throw new Error(
      `Frontend requer valores preenchidos para: ${missing.join(", ")}`
    );
  }

  if (!isProductionEnvironment()) {
    return;
  }

  const weak: string[] = [];

  if (isTooShortForProduction(process.env.INTERNAL_SERVICE_TOKEN)) {
    weak.push("INTERNAL_SERVICE_TOKEN");
  }

  if (isTooShortForProduction(process.env.BETTER_AUTH_SECRET)) {
    weak.push("BETTER_AUTH_SECRET");
  }

  if (weak.length > 0) {
    throw new Error(
      `Frontend em production requer valores fortes para: ${weak.join(", ")}`
    );
  }
}

export function canAutoBootstrapAdmin(): boolean {
  return !isProductionEnvironment();
}

// --- Studio v0.1: branding por instância (Forma C) ---

export type BrandConfig =
  | { kind: "solid"; color: string }
  | { kind: "gradient"; angle: string; from: string; to: string };

function parseBrand(raw: string): BrandConfig {
  try {
    const idx = raw.indexOf(":");
    if (idx === -1) return { kind: "solid", color: "#7E22CE" };
    const kind = raw.slice(0, idx).trim();
    const rest = raw.slice(idx + 1).trim();

    if (kind === "solid" && rest) {
      return { kind: "solid", color: rest };
    }
    if (kind === "gradient" && rest) {
      const parts = rest.split(",").map((p) => p.trim());
      if (parts.length === 3) {
        return { kind: "gradient", angle: parts[0], from: parts[1], to: parts[2] };
      }
    }
  } catch {
    // fallthrough
  }
  return { kind: "solid", color: "#7E22CE" };
}

function parseFeatures(raw: string): Set<string> {
  return new Set(
    raw
      .split(",")
      .map((f) => f.trim().toLowerCase())
      .filter(Boolean)
  );
}

export const studioConfig = {
  name: process.env.NEXT_PUBLIC_STUDIO_NAME ?? "Gyros Studio",
  agentName: process.env.NEXT_PUBLIC_AGENT_NAME ?? "Lyra",
  brand: parseBrand(
    process.env.NEXT_PUBLIC_STUDIO_BRAND ?? "gradient:135deg,#9333EA,#7E22CE"
  ),
  features: parseFeatures(
    process.env.NEXT_PUBLIC_FEATURES_ENABLED ?? "kb,chat,internal"
  ),
} as const;

export type StudioConfig = typeof studioConfig;
