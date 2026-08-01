// Client-side mirror of the cloud compute pricing model (kept in lockstep with
// bionodulo-website apps/web/lib/resource-profiles.ts). Used by the editor's
// Compute panel to show quick-size shortcuts, slider bounds, and a live
// credit/hr quote without a round-trip. The server re-validates + re-prices on
// submit, so this is purely for UX — never trusted for billing.

export type ResourceProfile =
  | 'micro' | 'small' | 'medium' | 'large' | 'xlarge' | 'extreme';

// Published customer sell-rates (credits/second). 1 credit = $0.01. Mirror of
// the server's VCPU_CREDIT_RATE / RAM_GB_CREDIT_RATE.
// Repriced 2026-08-01. Mirror of the server's rates in
// bionodulo-website apps/web/lib/resource-profiles.ts -- the server re-prices on
// submit, so these exist only to quote the same number in the Compute panel.
export const VCPU_CREDIT_RATE = 0.00127;
export const RAM_GB_CREDIT_RATE = 0.000195;
export const MIN_GB_PER_VCPU = 4;

/** Credits/second for an arbitrary spec (max of CPU- and RAM-derived). */
export function customComputeRate(vcpu: number, ramGb: number): number {
  return Math.max(
    Math.max(0, vcpu) * VCPU_CREDIT_RATE,
    Math.max(0, ramGb) * RAM_GB_CREDIT_RATE,
  );
}

export interface QuickSize {
  label: string;
  vcpu: number;
  ramGb: number;
}

/**
 * Convenience "quick pick" sizes — NOT locked tiers. Each just sets a custom
 * {vcpu, ramGb}; users can also freely slide to anything within their plan cap.
 */
export const QUICK_SIZES: QuickSize[] = [
  { label: 'XS', vcpu: 2, ramGb: 16 },
  { label: 'S', vcpu: 4, ramGb: 16 },
  { label: 'M', vcpu: 8, ramGb: 64 },
  { label: 'L', vcpu: 16, ramGb: 128 },
  { label: 'XL', vcpu: 32, ramGb: 256 },
  { label: 'XXL', vcpu: 64, ramGb: 512 },
];

/**
 * A run's compute size. The editor now always emits a custom {vcpu, ramGb};
 * the `profile` variant is retained only for backward-compat deserialization.
 */
export type ComputeSpec =
  | { kind: 'profile'; profile: ResourceProfile }
  | { kind: 'custom'; vcpu: number; ramGb: number };

/** Coerce any spec into concrete vCPU/RAM (legacy profiles map to a size). */
export function specDims(spec: ComputeSpec): { vcpu: number; ramGb: number } {
  if (spec.kind === 'custom') return { vcpu: spec.vcpu, ramGb: spec.ramGb };
  const map: Record<ResourceProfile, { vcpu: number; ramGb: number }> = {
    micro: { vcpu: 1, ramGb: 4 },
    small: { vcpu: 2, ramGb: 16 },
    medium: { vcpu: 8, ramGb: 64 },
    large: { vcpu: 16, ramGb: 128 },
    xlarge: { vcpu: 32, ramGb: 256 },
    extreme: { vcpu: 64, ramGb: 512 },
  };
  return map[spec.profile] ?? { vcpu: 2, ramGb: 16 };
}

export function specCreditPerSecond(spec: ComputeSpec): number {
  const { vcpu, ramGb } = specDims(spec);
  return customComputeRate(vcpu, ramGb);
}

export function specCreditsPerHour(spec: ComputeSpec): number {
  return Math.round(specCreditPerSecond(spec) * 3600);
}

export function specLabel(spec: ComputeSpec): string {
  const { vcpu, ramGb } = specDims(spec);
  return `${vcpu} vCPU / ${ramGb} GB`;
}

export interface ComputeCaps {
  maxRamGb: number;
  maxVcpu: number;
  /** Free is capped; everyone can pick custom (no locked-preset tier anymore). */
  allowsCustom: boolean;
}

/**
 * Per-plan max RAM (GB), mirroring the server. 0 = unlimited (paid plans let the
 * user choose any size). Free is the only capped tier.
 */
export const PLAN_MAX_RAM_GB: Record<string, number> = {
  free: 16,
  starter: 0,
  professional: 0,
  team: 0,
  enterprise: 0,
};

/** Per-plan caps (mirror of the server computeCapsForPlan). */
export function computeCapsForPlan(plan: string | null, maxRamGb: number): ComputeCaps {
  if (!plan || plan === 'free') {
    return { maxRamGb: 16, maxVcpu: 4, allowsCustom: true };
  }
  const cap = maxRamGb > 0 ? maxRamGb : 4096;
  return {
    maxRamGb: cap,
    maxVcpu: Math.max(1, Math.floor(cap / MIN_GB_PER_VCPU)),
    allowsCustom: true,
  };
}

/** Caps for a plan name, looking up its RAM limit from PLAN_MAX_RAM_GB. */
export function capsForPlanName(plan: string | null): ComputeCaps {
  return computeCapsForPlan(plan, PLAN_MAX_RAM_GB[plan ?? 'free'] ?? 16);
}

/** Whether a size is within a plan's caps. */
export function sizeAllowed(caps: ComputeCaps, vcpu: number, ramGb: number): boolean {
  return vcpu <= caps.maxVcpu && ramGb <= caps.maxRamGb;
}

/** Serialize a ComputeSpec into the /api/runs request shape (always custom). */
export function specToRunBody(spec: ComputeSpec): {
  compute?: { vcpu: number; ramGb: number };
} {
  const { vcpu, ramGb } = specDims(spec);
  return { compute: { vcpu, ramGb } };
}
