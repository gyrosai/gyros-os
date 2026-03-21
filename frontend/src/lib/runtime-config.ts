const MIN_PRODUCTION_SECRET_LENGTH = 32;

function normalize(value: string | undefined): string {
  return (value || "").trim();
}

export function isProductionEnvironment(): boolean {
  return normalize(process.env.ENVIRONMENT).toLowerCase() === "production";
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
