// Client-side mirror of the cloud compute pricing model (kept in lockstep with
// bionodulo-website apps/web/lib/resource-profiles.ts). Used by the editor's
// Compute panel to show slider bounds, a live credit/hr quote, and a
// workflow-derived size recommendation without a round-trip. The server
// re-validates + re-prices on submit, so this is purely for UX — never trusted
// for billing.

export type ResourceProfile =
  | 'micro' | 'small' | 'medium' | 'large' | 'gpu' | 'xlarge' | 'extreme';

// Published customer sell-rates (credits/second). 1 credit = $0.01. Mirror of
// the server's VCPU_CREDIT_RATE / RAM_GB_CREDIT_RATE.
// Repriced 2026-08-01. Mirror of the server's rates in
// bionodulo-website apps/web/lib/resource-profiles.ts -- the server re-prices on
// submit, so these exist only to quote the same number in the Compute panel.
export const VCPU_CREDIT_RATE = 0.00127;
export const RAM_GB_CREDIT_RATE = 0.000195;
export const MIN_GB_PER_VCPU = 4;

/**
 * Per-A10-GPU sell-rate (credits/second), mirror of the server's
 * GPU_A10_CREDIT_PER_SECOND. The GPU base is priced from OCI's A10 (its
 * primary accelerator), not the old AWS T4 pin; the user's chosen vCPU/RAM is
 * billed on top via the regular formula.
 */
export const GPU_A10_CREDIT_PER_SECOND = 0.025;

/** GPU worker sizing bounds + count bounds (mirror of the server). */
export const GPU_MIN_VCPU = 4;
export const GPU_MAX_VCPU = 64;
export const GPU_MIN_RAM_GB = 16;
export const GPU_MAX_RAM_GB = 256;
export const GPU_MIN_COUNT = 1;
export const GPU_MAX_COUNT = 4;
export const GPU_BASE_VCPU = 4;
export const GPU_BASE_RAM_GB = 16;

/** Credits/second for a GPU worker: A10 base per GPU + the CPU/RAM formula. */
export function gpuComputeRate(vcpu: number, ramGb: number, gpuCount = 1): number {
  const gpus = Math.max(GPU_MIN_COUNT, Math.min(GPU_MAX_COUNT, Math.round(gpuCount)));
  return gpus * GPU_A10_CREDIT_PER_SECOND + customComputeRate(vcpu, ramGb);
}

/** Credits/second for an arbitrary spec (max of CPU- and RAM-derived). */
export function customComputeRate(vcpu: number, ramGb: number): number {
  return Math.max(
    Math.max(0, vcpu) * VCPU_CREDIT_RATE,
    Math.max(0, ramGb) * RAM_GB_CREDIT_RATE,
  );
}

/**
 * A run's compute size. The editor emits a custom {vcpu, ramGb} for CPU-only
 * sizes and a GPU spec (dims + A10 count) for GPU workers; the `profile`
 * variant is retained only for backward-compat deserialization of old
 * localStorage values — the UI no longer offers named presets.
 */
export type ComputeSpec =
  | { kind: 'profile'; profile: ResourceProfile }
  | { kind: 'gpu'; vcpu: number; ramGb: number; gpuCount?: number }
  | { kind: 'custom'; vcpu: number; ramGb: number };

/** True when the spec runs on the GPU worker (A10, auto-matched instance). */
export function isGpuSpec(spec: ComputeSpec): boolean {
  return spec.kind === 'gpu' || (spec.kind === 'profile' && spec.profile === 'gpu');
}

/** GPU count of a spec (0 for CPU-only). */
export function specGpuCount(spec: ComputeSpec): number {
  if (spec.kind === 'gpu') {
    return Math.max(GPU_MIN_COUNT, Math.min(GPU_MAX_COUNT, Math.round(spec.gpuCount ?? 1)));
  }
  return 0;
}

/** Coerce any spec into concrete vCPU/RAM (legacy profiles map to a size). */
export function specDims(spec: ComputeSpec): { vcpu: number; ramGb: number } {
  if (spec.kind === 'custom' || spec.kind === 'gpu') {
    return { vcpu: spec.vcpu, ramGb: spec.ramGb };
  }
  const map: Record<ResourceProfile, { vcpu: number; ramGb: number }> = {
    micro: { vcpu: 1, ramGb: 4 },
    small: { vcpu: 2, ramGb: 16 },
    medium: { vcpu: 8, ramGb: 64 },
    large: { vcpu: 16, ramGb: 128 },
    gpu: { vcpu: GPU_BASE_VCPU, ramGb: GPU_BASE_RAM_GB },
    xlarge: { vcpu: 32, ramGb: 256 },
    extreme: { vcpu: 64, ramGb: 512 },
  };
  return map[spec.profile] ?? { vcpu: 2, ramGb: 16 };
}

/** Clamp a GPU selection into the server's GPU bounds. */
export function clampGpuSpec(
  vcpu: number,
  ramGb: number,
  gpuCount = GPU_MIN_COUNT,
): { vcpu: number; ramGb: number; gpuCount: number } {
  return {
    vcpu: Math.min(GPU_MAX_VCPU, Math.max(GPU_MIN_VCPU, Math.round(vcpu))),
    ramGb: Math.min(GPU_MAX_RAM_GB, Math.max(GPU_MIN_RAM_GB, Math.round(ramGb))),
    gpuCount: Math.min(GPU_MAX_COUNT, Math.max(GPU_MIN_COUNT, Math.round(gpuCount))),
  };
}

export function specCreditPerSecond(spec: ComputeSpec): number {
  // GPU workers are priced by accelerator + the CPU/RAM formula.
  if (isGpuSpec(spec)) {
    const { vcpu, ramGb } = specDims(spec);
    return gpuComputeRate(vcpu, ramGb, specGpuCount(spec));
  }
  const dims = specDims(spec);
  return customComputeRate(dims.vcpu, dims.ramGb);
}

export function specCreditsPerHour(spec: ComputeSpec): number {
  return Math.round(specCreditPerSecond(spec) * 3600);
}

export function specLabel(spec: ComputeSpec): string {
  const { vcpu, ramGb } = specDims(spec);
  if (isGpuSpec(spec)) {
    const gpus = specGpuCount(spec);
    return `${vcpu} vCPU / ${ramGb} GB · ${gpus > 1 ? `A10 ×${gpus}` : 'A10'} (auto-matched)`;
  }
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

/**
 * Serialize a ComputeSpec into the /api/runs request shape. CPU sizes go as a
 * custom {vcpu, ramGb}; GPU workers go as `resourceProfile: 'gpu'` (the
 * accelerator cannot be expressed as CPU/RAM) with gpuCount and the worker's
 * customVcpu/customMemoryGb when it differs from the base. Legacy CPU profile
 * specs still map to their custom dims for backward compatibility.
 */
export function specToRunBody(spec: ComputeSpec): {
  resourceProfile?: string;
  compute?: { vcpu: number; ramGb: number };
  customVcpu?: number;
  customMemoryGb?: number;
  gpuCount?: number;
} {
  if (spec.kind === 'gpu') {
    const { vcpu, ramGb, gpuCount } = clampGpuSpec(spec.vcpu, spec.ramGb, spec.gpuCount ?? 1);
    const body: {
      resourceProfile: string;
      customVcpu?: number;
      customMemoryGb?: number;
      gpuCount?: number;
    } = { resourceProfile: 'gpu' };
    // The GPU BASE dims need no override; anything else sizes the worker.
    if (vcpu !== GPU_BASE_VCPU || ramGb !== GPU_BASE_RAM_GB) {
      body.customVcpu = vcpu;
      body.customMemoryGb = ramGb;
    }
    if (gpuCount > GPU_MIN_COUNT) body.gpuCount = gpuCount;
    return body;
  }
  if (spec.kind === 'profile' && spec.profile === 'gpu') {
    return { resourceProfile: 'gpu' };
  }
  const { vcpu, ramGb } = specDims(spec);
  return { compute: { vcpu, ramGb } };
}

// ---------------------------------------------------------------------------
// Workflow auto-sizing
// ---------------------------------------------------------------------------

/** Node slice the recommender needs — WorkflowNode is structurally compatible. */
export interface RecommenderNode {
  id: string;
  type: string;
  params?: Record<string, unknown>;
}

export interface RecommenderEdge {
  from?: { node?: string } | null;
  to?: { node?: string } | null;
}

/** Minimal objectInfo entry shape the recommender reads. */
interface RecommenderMeta {
  requires_gpu?: boolean;
  input_types?: {
    required?: Record<string, { default?: unknown; min?: number; max?: number }>;
    optional?: Record<string, { default?: unknown; min?: number; max?: number }>;
  };
}

export interface RecommendedSpec {
  vcpu: number;
  ramGb: number;
  /** 0 = CPU-only; 1 = a GPU node is present (the worker is one A10 host). */
  gpuCount: number;
  /** Human-readable basis shown next to the recommendation. */
  basis: string;
}

function nodeThreads(node: RecommenderNode, meta?: RecommenderMeta): number {
  const raw = node.params?.threads;
  if (typeof raw === 'number' && Number.isFinite(raw) && raw >= 1) {
    return Math.min(64, Math.round(raw));
  }
  const spec = meta?.input_types?.required?.threads ?? meta?.input_types?.optional?.threads;
  if (spec) {
    const def = typeof spec.default === 'number' ? spec.default : NaN;
    if (Number.isFinite(def) && def >= 1) return Math.min(64, Math.round(def));
  }
  return 1;
}

/**
 * Recommend a compute size for a workflow graph.
 *
 * vCPU: the engine executes independent nodes concurrently (workers scale to
 * the machine's vCPUs) and threads-bound nodes each claim their `threads`
 * count. The busiest topological "stage" — the level whose summed threads is
 * highest — is therefore the peak demand a right-sized machine should cover.
 * RAM: 4 GB per recommended vCPU (the platform minimum), which covers the
 * common aligner/QC tools that thread-scale their memory. GPU: any node that
 * declares `requires_gpu` routes the run to the A10 worker.
 */
export function recommendComputeSpec(
  nodes: RecommenderNode[],
  edges: RecommenderEdge[],
  objectInfo: Record<string, RecommenderMeta | undefined>,
): RecommendedSpec {
  if (nodes.length === 0) {
    return { vcpu: 2, ramGb: 8, gpuCount: 0, basis: 'empty workflow' };
  }

  const metaOf = (type: string) => objectInfo[type];
  let gpuCount = 0;
  const threadsById = new Map<string, number>();
  for (const node of nodes) {
    const meta = metaOf(node.type);
    if (meta?.requires_gpu) gpuCount = 1;
    threadsById.set(node.id, nodeThreads(node, meta));
  }

  // Longest-path depth per node; depth groups approximate concurrent stages.
  const parents = new Map<string, string[]>();
  for (const node of nodes) parents.set(node.id, []);
  for (const edge of edges) {
    const from = edge?.from?.node;
    const to = edge?.to?.node;
    if (from && to && parents.has(to) && threadsById.has(from)) {
      parents.get(to)!.push(from);
    }
  }
  const depth = new Map<string, number>();
  const resolveDepth = (id: string, seen: Set<string>): number => {
    if (depth.has(id)) return depth.get(id)!;
    if (seen.has(id)) return 0; // cycle guard — treat as a root
    seen.add(id);
    let d = 0;
    for (const p of parents.get(id) ?? []) {
      d = Math.max(d, resolveDepth(p, seen) + 1);
    }
    seen.delete(id);
    depth.set(id, d);
    return d;
  };
  const stageThreads = new Map<number, number>();
  for (const node of nodes) {
    const d = resolveDepth(node.id, new Set());
    stageThreads.set(d, (stageThreads.get(d) ?? 0) + (threadsById.get(node.id) ?? 1));
  }
  let peak = 0;
  for (const v of stageThreads.values()) peak = Math.max(peak, v);
  peak = Math.max(peak, 2);

  if (gpuCount > 0) {
    const vcpu = Math.max(GPU_MIN_VCPU, Math.min(GPU_MAX_VCPU, peak));
    const ramGb = Math.max(GPU_MIN_RAM_GB, vcpu * MIN_GB_PER_VCPU);
    return {
      vcpu,
      ramGb: Math.min(GPU_MAX_RAM_GB, ramGb),
      gpuCount,
      basis: `GPU node in graph · busiest stage ${peak} threads`,
    };
  }
  const vcpu = Math.min(64, peak);
  return {
    vcpu,
    ramGb: Math.max(4, vcpu * MIN_GB_PER_VCPU),
    gpuCount: 0,
    basis: `busiest stage ${peak} threads · ${nodes.length} node${nodes.length === 1 ? '' : 's'}`,
  };
}

/** One-line summary of a recommendation for the panel's auto-size row. */
export function computeAutoNote(rec: RecommendedSpec): string {
  const size = rec.gpuCount > 0
    ? `${rec.vcpu} vCPU / ${rec.ramGb} GB · A10`
    : `${rec.vcpu} vCPU / ${rec.ramGb} GB`;
  return `${size} — ${rec.basis}`;
}

/** Clamp a recommendation into a plan's caps (and GPU bounds when GPU). */
export function specFromRecommendation(
  rec: RecommendedSpec,
  caps: ComputeCaps,
): ComputeSpec {
  if (rec.gpuCount > 0) {
    const gpuMaxVcpu = Math.min(GPU_MAX_VCPU, caps.maxVcpu);
    const gpuMaxRam = Math.min(GPU_MAX_RAM_GB, caps.maxRamGb);
    const clamped = clampGpuSpec(
      Math.min(gpuMaxVcpu, rec.vcpu),
      Math.min(gpuMaxRam, rec.ramGb),
      1,
    );
    return { kind: 'gpu', ...clamped };
  }
  const vcpu = Math.min(caps.maxVcpu, Math.max(1, rec.vcpu));
  const ramGb = Math.min(caps.maxRamGb, Math.max(vcpu * MIN_GB_PER_VCPU, rec.ramGb));
  return { kind: 'custom', vcpu, ramGb };
}
