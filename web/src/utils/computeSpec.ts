// Client-side mirror of the cloud compute pricing model (kept in lockstep with
// bionodulo-website apps/web/lib/resource-profiles.ts). Used by the editor's
// Compute panel to show preset chips, slider bounds, and a live credit/hr quote
// without a round-trip. The server re-validates + re-prices on submit, so this
// is purely for UX — never trusted for billing.

export type ResourceProfile =
  | 'micro' | 'small' | 'medium' | 'large' | 'xlarge' | 'extreme';

export interface PresetSpec {
  profile: ResourceProfile;
  label: string;
  vcpu: number;
  ramGb: number;
  creditPerSecond: number;
}

/** The six presets, mirroring the server's RESOURCE_PROFILES. */
export const PRESETS: PresetSpec[] = [
  { profile: 'micro', label: 'Micro', vcpu: 1, ramGb: 4, creditPerSecond: 0.02 },
  { profile: 'small', label: 'Small', vcpu: 2, ramGb: 16, creditPerSecond: 0.08 },
  { profile: 'medium', label: 'Medium', vcpu: 8, ramGb: 64, creditPerSecond: 0.32 },
  { profile: 'large', label: 'Large', vcpu: 16, ramGb: 128, creditPerSecond: 0.64 },
  { profile: 'xlarge', label: 'XLarge', vcpu: 32, ramGb: 256, creditPerSecond: 1.28 },
  { profile: 'extreme', label: 'Extreme', vcpu: 64, ramGb: 1024, creditPerSecond: 5.12 },
];

export const VCPU_CREDIT_RATE = 0.04;
export const RAM_GB_CREDIT_RATE = 0.005;
export const MIN_GB_PER_VCPU = 4;

/** A run's compute size: a named preset or an arbitrary custom spec. */
export type ComputeSpec =
  | { kind: 'profile'; profile: ResourceProfile }
  | { kind: 'custom'; vcpu: number; ramGb: number };

/** Credits/second for an arbitrary custom spec (max of CPU- and RAM-derived). */
export function customComputeRate(vcpu: number, ramGb: number): number {
  return Math.max(
    Math.max(0, vcpu) * VCPU_CREDIT_RATE,
    Math.max(0, ramGb) * RAM_GB_CREDIT_RATE,
  );
}

export function presetFor(profile: ResourceProfile): PresetSpec {
  return PRESETS.find(p => p.profile === profile) ?? PRESETS[1];
}

export function specCreditPerSecond(spec: ComputeSpec): number {
  return spec.kind === 'profile'
    ? presetFor(spec.profile).creditPerSecond
    : customComputeRate(spec.vcpu, spec.ramGb);
}

export function specCreditsPerHour(spec: ComputeSpec): number {
  return Math.round(specCreditPerSecond(spec) * 3600);
}

export function specLabel(spec: ComputeSpec): string {
  return spec.kind === 'profile'
    ? presetFor(spec.profile).label
    : `${spec.vcpu} vCPU / ${spec.ramGb} GB`;
}

export interface ComputeCaps {
  maxRamGb: number;
  maxVcpu: number;
  allowsCustom: boolean;
  allowedProfiles: ResourceProfile[];
}

/** Per-plan max RAM (GB), mirroring PRICING_TIERS.maxRamGb. 0 = unlimited. */
export const PLAN_MAX_RAM_GB: Record<string, number> = {
  free: 16,
  starter: 64,
  professional: 128,
  team: 256,
  enterprise: 0,
};

/** Per-plan caps (mirror of the server). `maxRamGb` is the plan's RAM limit. */
export function computeCapsForPlan(plan: string | null, maxRamGb: number): ComputeCaps {
  if (!plan || plan === 'free') {
    return { maxRamGb: 16, maxVcpu: 2, allowsCustom: false, allowedProfiles: ['micro', 'small'] };
  }
  const cap = maxRamGb > 0 ? maxRamGb : 1024;
  return {
    maxRamGb: cap,
    maxVcpu: Math.max(1, Math.floor(cap / MIN_GB_PER_VCPU)),
    allowsCustom: true,
    allowedProfiles: PRESETS.filter(p => p.ramGb <= cap).map(p => p.profile),
  };
}

/** Caps for a plan name, looking up its RAM limit from PLAN_MAX_RAM_GB. */
export function capsForPlanName(plan: string | null): ComputeCaps {
  return computeCapsForPlan(plan, PLAN_MAX_RAM_GB[plan ?? 'free'] ?? 16);
}

/** Serialize a ComputeSpec into the /api/runs request shape. */
export function specToRunBody(spec: ComputeSpec): {
  resourceProfile?: string;
  compute?: { vcpu: number; ramGb: number };
} {
  return spec.kind === 'profile'
    ? { resourceProfile: spec.profile }
    : { compute: { vcpu: spec.vcpu, ramGb: spec.ramGb } };
}
