export interface InputSpec {
  type: string;
  default?: unknown;
  options?: string[];
  tooltip?: string;
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
  experimental?: boolean;
  requires_external_tools?: string[];
  documentation_url?: string;
  version?: string;
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
  ui?: {
    title?: string;
    color?: string;
    collapsed?: boolean;
    pinned?: boolean;
    muted?: boolean;
    bypassed?: boolean;
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

export interface Workflow {
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
  status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled';
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
}

export interface ManagerStatus {
  custom_nodes_dir: string;
  installed_packages: string[];
  installed_node_modules: string[];
  environment_info: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
}

export interface EnvironmentSpec {
  type: 'conda' | 'mamba' | 'micromamba' | 'docker' | 'apptainer' | 'singularity' | 'none';
  name?: string;
  file?: string;
  image?: string;
  channels?: string[];
  packages?: string[];
  pip?: string[];
  mounts?: string[];
  notes?: string;
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

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  tools: string[];
  node_count: number;
  filename: string;
}
