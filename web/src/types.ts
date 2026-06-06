export interface InputSpec {
  type: string;
  default?: unknown;
  options?: string[];
  tooltip?: string;
  description?: string;
  min?: number;
  max?: number;
  step?: number;
  label?: string;
  link?: boolean;
  forceInput?: boolean;
  advanced?: boolean;
  multiline?: boolean;
  display?: 'number' | 'slider' | 'default';
  accept?: string;
  directory?: boolean;
}

export interface NodeMetadata {
  id: string;
  display_name: string;
  category: string;
  description?: string;
  search_aliases?: string[];
  input_types?: {
    required?: Record<string, InputSpec>;
    optional?: Record<string, InputSpec>;
    hidden?: Record<string, InputSpec>;
  };
  return_types?: string[];
  return_names?: string[];
  output_node?: boolean;
  visual_only?: boolean;
  experimental?: boolean;
  requires_external_tools?: string[];
  documentation_url?: string;
  version?: string;
  deprecation_message?: string;
  replaced_by?: string;
  lifecycle?: {
    status?: 'active' | 'deprecated' | string;
    deprecated?: boolean;
    deprecation_message?: string;
    replaced_by?: string;
  };
  versioning?: {
    current?: string;
    previous: string[];
    migrations: Array<{
      from_version?: string;
      to_version?: string;
      description?: string;
      [key: string]: unknown;
    }>;
  };
  environment?: string;
  function?: string;
  deprecated?: boolean;
}

export interface ObjectInfo {
  [nodeId: string]: NodeMetadata;
}

export interface WorkflowNode {
  id: string;
  type: string;
  position: [number, number];
  params: Record<string, unknown>;
  node_info?: NodeMetadata;
  // Optional parent reference. Today reroutes use it to inherit the group
  // of the edge they were inserted on so move/select operations on the
  // group also move the reroute. Subgraph nodes can use the same field.
  parentId?: string;
  ui?: {
    title?: string;
    color?: string;
    shape?: 'round' | 'box' | 'card';
    collapsed?: boolean;
    pinned?: boolean;
    muted?: boolean;
    bypassed?: boolean;
    width?: number;
    height?: number;
  };
}

export interface WorkflowEdge {
  id: string;
  from: { node: string; output: string };
  to: { node: string; input: string };
}

export interface WorkflowGroup {
  id: string;
  name: string;
  position: [number, number];
  width: number;
  height: number;
  color: string;
  collapsed: boolean;
  selected?: boolean;
}

export interface WorkflowParameter {
  name: string;
  type: string;
  required?: boolean;
  default?: unknown;
  value?: unknown;
  description?: string;
}

export interface Workflow {
  id?: string;
  version: string;
  app: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  groups: WorkflowGroup[];
  outputs: Record<string, string>;
  environment?: Record<string, unknown>;
  dependencies?: Record<string, string>;
  parameters?: WorkflowParameter[];
}

export interface NodeStatus {
  node_id: string;
  status: 'pending' | 'running' | 'cached' | 'completed' | 'error' | 'skipped';
  started_at?: string;
  ended_at?: string;
  error?: string;
  log_url?: string;
  outputs?: Record<string, string>;
}

export interface RunRecord {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled' | 'dry_run';
  workflow_name: string;
  node_statuses: NodeStatus[];
  node_outputs: Record<string, Record<string, string>>;
  execution_plan: string[];
  previews: Record<string, string>;
  artifacts: Record<string, string>;
  start_time?: string;
  end_time?: string;
  options?: Record<string, unknown>;
  error?: string;
}

export interface QueueState {
  running: RunRecord | null;
  pending: RunRecord[];
}

export interface LogEntry {
  run_id: string;
  node_id: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
  timestamp: string;
  detail?: string;
}

export interface ManagerStatus {
  custom_nodes_dir: string;
  installed_nodes: ManagerInstalledNode[];
  total: number;
}

export interface ManagerInstalledNode {
  name: string;
  version: string;
  category: string;
  builtin: boolean;
}

export interface EnvironmentSpec {
  type: 'pixi' | 'docker' | 'apptainer' | 'singularity' | 'none';
  name?: string;
  file?: string;
  image?: string;
  channels?: string[];
  packages?: string[];
  pip?: string[];
  mounts?: string[];
  notes?: string;
}

export interface PixiEnvironment {
  name: string;
  path: string;
  active: boolean;
}

export interface EnvPackage {
  name: string;
  version: string;
  channel: string;
  build: string;
}

export interface DependencyStatus {
  name: string;
  type: 'node' | 'executable' | 'package';
  status: 'installed' | 'missing' | 'installing' | 'error';
  source: string;
  message: string;
  envs: string[];
}

export interface HPCConfig {
  enabled: boolean;
  backend: 'slurm' | 'pbs' | 'sge';
  partition?: string;
  account?: string;
  modules?: string[];
  container?: string;
  walltime?: string;
  cpus_per_task?: number;
  mem_per_cpu?: string;
  extra_args?: string;
}

export interface ExportRequest {
  workflow: Workflow;
  format: 'snakemake' | 'nextflow' | 'cwl' | 'galaxy';
}

export interface ImportRequest {
  source: string;
  format: 'snakemake' | 'nextflow' | 'cwl' | 'galaxy';
}

export interface MissingNode {
  node_type: string;
  git_url: string;
  git_commit: string;
  requirements: string[];
  message: string;
}

export interface MissingExecutable {
  name: string;
  conda_package: string;
  node_types: string[];
  message: string;
  recommended_env?: string;
  category?: string;
}

export interface MissingPackage {
  name: string;
  source: string;
  node_types: string[];
  message: string;
}

export interface MissingRPackage {
  name: string;
  source: string;
  node_types: string[];
  message: string;
  recommended_env?: string;
}

export interface ResolveReport {
  missing_nodes: MissingNode[];
  missing_executables: MissingExecutable[];
  missing_packages: MissingPackage[];
  missing_r_packages: MissingRPackage[];
  required_packages: string[];
  env_id: string;
  env_ready: boolean;
  installable: boolean;
  errors: string[];
  has_issues: boolean;
  summary: string;
}

export interface InstallJobStatus {
  job_id: string;
  status: string;
  total_steps: number;
  completed_steps: number;
  current_step: string;
  message: string;
  errors: string[];
  percent: number;
}

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  tools: string[];
  preview_steps?: string[];
  node_count: number;
  filename: string;
}

export interface HostCheck {
  available: boolean;
  path: string | null;
  required: boolean;
  auto_installable: boolean;
  description: string;
}

export interface HostStatus {
  ready: boolean;
  checks: Record<string, HostCheck>;
  missing_required: string[];
  missing_optional: string[];
  message: string;
}
