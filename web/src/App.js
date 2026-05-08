import React, { useCallback, useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import {
  ReactFlow,
  Background,
  Handle,
  Position,
  BaseEdge,
  MiniMap,
  NodeResizer,
  addEdge,
  getBezierPath,
  reconnectEdge,
  useEdgesState,
  useNodesState,
} from "https://esm.sh/@xyflow/react@12.6.0?deps=react@18.3.1,react-dom@18.3.1";

const h = React.createElement;
const EDGE_PALETTE = ["#38bdf8", "#a78bfa", "#f59e0b", "#22c55e", "#fb7185", "#14b8a6", "#f97316", "#60a5fa"];

const STATUS_LABELS = {
  idle: "idle",
  invalid: "invalid",
  queued: "queued",
  running: "running",
  cached: "cached",
  completed: "completed",
  failed: "failed",
  blocked: "blocked",
  interrupted: "interrupted",
  muted: "muted",
  bypassed: "bypassed",
};

const COMMON_NODE_IDS = ["input_fastq", "fastqc", "fastp", "collect_files", "multiqc"];
const NODE_WIDTH = 235;
const NODE_HEIGHT = 136;
const EMPTY_WORKFLOW = { nodes: [], edges: [], groups: [] };
const DEFAULT_ENVIRONMENT = {
  type: "conda",
  name: "bionodulo-workflow",
  file: "envs/workflow.yaml",
  image: "",
  channels: ["conda-forge", "bioconda"],
  packages: ["fastqc", "fastp", "multiqc"],
  pip: [],
  mounts: [],
  notes: "",
};
const DEFAULT_LLM_SETTINGS = {
  provider: "openai",
  model: "gpt-4.1-mini",
  base_url: "",
  api_key: "",
  temperature: 0.2,
};
const LEFT_RAIL_ITEMS = [
  { id: "data", label: "Data", icon: "folder", description: "Explore the project workspace, inputs, runs, and generated workflow results." },
  { id: "nodes", label: "Nodes", icon: "nodes", description: "Browse available bioinformatics nodes grouped by category." },
  { id: "templates", label: "Templates", icon: "templates", description: "Start from common bioinformatics workflow templates." },
  { id: "envs", label: "Envs", icon: "terminal", description: "Create, select, and install reproducible Conda, Docker, or Apptainer environments." },
  { id: "help", label: "Help", icon: "help", description: "Canvas gestures: right-click or double-click canvas to add nodes; double-click nodes to edit." },
  { id: "console", label: "Console", icon: "console", description: "Execution diagnostics and node logs." },
  { id: "settings", label: "Settings", icon: "settings", description: "BioNodulo interface and execution preferences." },
];
const ICON_PATHS = {
  folder: "M3 6.5A2.5 2.5 0 0 1 5.5 4H10l2 2h6.5A2.5 2.5 0 0 1 21 8.5v8A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z",
  refresh: "M20 6v5h-5M4 18v-5h5M18.2 9A7 7 0 0 0 6.4 6.2L4 8.5M5.8 15A7 7 0 0 0 17.6 17.8L20 15.5",
  nodes: "M7 7h4v4H7zM14 13h4v4h-4zM6 16h4v4H6zM11 9h2.5a2.5 2.5 0 0 1 2.5 2.5V13M10 18h2a2 2 0 0 0 2-2v-1",
  templates: "M6 3h9l3 3v15H6zM15 3v4h4M9 10h6M9 14h6M9 18h4",
  terminal: "M4 6h16v12H4zM7 10l3 2-3 2M12 15h5",
  snake: "M6 6c2-3 7-3 9 0 1.8 2.7-.3 5-3.5 4.2-2.6-.5-2.9-3.2-.8-3.9 2.2-.8 4.7.8 4.5 3.3-.2 2.7-3 4.7-6.2 4.2-2.8-.4-4.8-2.1-4.8-4.2M15 6h.01",
  docker: "M4 13h16l-1.2 3.4A4 4 0 0 1 15 19H8.5A4.5 4.5 0 0 1 4 14.5V13M6 10h3v3H6zM10 10h3v3h-3zM14 10h3v3h-3zM10 7h3v3h-3zM18 11c.8-1.2 1.7-1.8 3-1.8",
  apptainer: "M12 3l7.8 4.5v9L12 21l-7.8-4.5v-9zM12 7.2l4.2 2.4v4.8L12 16.8l-4.2-2.4V9.6z",
  fit: "M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4M9 9h6v6H9z",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6zM12 15v2",
  unlock: "M7 11V8a5 5 0 0 1 9.3-2.5M6 11h12v9H6zM12 15v2",
  help: "M12 18h.01M9.5 9a2.6 2.6 0 1 1 4.5 1.75c-.8.7-1.9 1.1-1.9 2.5v.35M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  console: "M4 5h16v14H4zM7 9l3 3-3 3M12 15h5",
  settings: "M12 8.4a3.6 3.6 0 1 1 0 7.2 3.6 3.6 0 0 1 0-7.2M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.8-1L14.4 3h-4.8l-.4 3.1a7 7 0 0 0-1.8 1l-2.4-1-2 3.4L5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.8 1l.4 3.1h4.8l.4-3.1a7 7 0 0 0 1.8-1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1",
  edit: "M16.5 4.5l3 3L7.5 19.5H4.5v-3L16.5 4.5z",
  copy: "M8 4h9a2 2 0 0 1 2 2v9M6 8H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-1",
  pin: "M14 14l-4 4M10 10l-2.5-2.5a2 2 0 0 1 0-2.83l.17-.17a2 2 0 0 1 2.83 0L13 7l-3 3 4 4zM12 12l4-4 2 2-4 4",
  "pin-off": "M14 14l-4 4M10 10l-2.5-2.5a2 2 0 0 1 0-2.83l.17-.17a2 2 0 0 1 2.83 0L13 7l-3 3 4 4zM12 12l4-4 2 2-4 4M3 3l18 18",
  mute: "M11 5L6 9H2v6h4l5 4V5zM23 9l-6 6M17 9l6 6",
  bypass: "M5 12l5-5v3h4l5-5v10l-5-5h-4v3l-5-5z",
  group: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  play: "M8 5.5v13l11-6.5z",
  validate: "M9 12l2 2 4-4M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  trash: "M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3",
  palette: "M12 3a9 9 0 0 0 0 18 2 2 0 0 0 2-2c0-.5-.2-1-.5-1.3-.3-.3-.5-.8-.5-1.2a2 2 0 0 1 2-2h2.5a6.5 6.5 0 0 0 6.5-6.5C24 6.8 18.5 3 12 3z",
  "more-vertical": "M12 6a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM12 13.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM12 21a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
  "more-horizontal": "M6 12a1.5 1.5 0 1 0-3 0 1.5 1.5 0 0 0 3 0zM13.5 12a1.5 1.5 0 1 0-3 0 1.5 1.5 0 0 0 3 0zM21 12a1.5 1.5 0 1 0-3 0 1.5 1.5 0 0 0 3 0z",
  paste: "M16 4h-2a2 2 0 0 0-4 0H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zM12 2a1 1 0 1 1 0 2 1 1 0 0 1 0-2z",
  "chevron-right": "M9 6l6 6-6 6",
  "move-to-group": "M4 4h16v16H4zM8 8h8v2H8zM8 12h8v2H8zM8 16h5v2H8z",
  "align-top": "M4 4h16v2H4zM7 8h10v10H7z",
  "align-bottom": "M4 18h16v2H7M7 4h10v10H7z",
  "align-left": "M4 4h2v16H4zM8 7h10v10H8z",
  "align-right": "M20 4h-2v16h2zM6 7h10v10H6z",
  "info-circle": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8h.01M11 12h1v4h1",
  "zoom-in": "M11 8v6M8 11h6M15 15l5 5",
  "zoom-out": "M8 11h6M15 15l5 5",
};
const WORKFLOW_TEMPLATES = [
  {
    id: "fastq-qc",
    name: "FASTQ QC and trimming",
    description: "Input FASTQ -> FastQC -> fastp -> FastQC -> MultiQC.",
    workflow: {
      version: "0.1.0",
      app: "bionodulo",
      name: "FASTQ QC and trimming",
      description: "Run quality control before and after trimming, then aggregate with MultiQC.",
      nodes: [
        { id: "input-fastq-1", type: "input_fastq", position: { x: 80, y: 150 }, params: { files: ["examples/data/sample_R1.fastq.gz", "examples/data/sample_R2.fastq.gz"] } },
        { id: "fastqc-raw", type: "fastqc", position: { x: 360, y: 110 }, params: { threads: 4 } },
        { id: "fastp-1", type: "fastp", position: { x: 640, y: 150 }, params: { threads: 4 } },
        { id: "fastqc-trimmed", type: "fastqc", position: { x: 920, y: 150 }, params: { threads: 4 } },
        { id: "collect-qc", type: "collect_files", position: { x: 1180, y: 130 }, params: {} },
        { id: "multiqc-1", type: "multiqc", position: { x: 1440, y: 130 }, params: {} },
      ],
      edges: [
        { id: "edge-raw-qc", from: { node: "input-fastq-1", output: "reads" }, to: { node: "fastqc-raw", input: "reads" } },
        { id: "edge-fastp", from: { node: "fastqc-raw", output: "reads" }, to: { node: "fastp-1", input: "reads" } },
        { id: "edge-trim-qc", from: { node: "fastp-1", output: "trimmed_reads" }, to: { node: "fastqc-trimmed", input: "reads" } },
        { id: "edge-collect-raw", from: { node: "fastqc-raw", output: "report_dir" }, to: { node: "collect-qc", input: "first" } },
        { id: "edge-collect-trim", from: { node: "fastqc-trimmed", output: "report_dir" }, to: { node: "collect-qc", input: "second" } },
        { id: "edge-multiqc", from: { node: "collect-qc", output: "directory" }, to: { node: "multiqc-1", input: "reports" } },
      ],
      outputs: ["multiqc-1"],
    },
  },
  {
    id: "bwa-bam",
    name: "BWA alignment skeleton",
    description: "Reference FASTA + FASTQ reads -> BWA mem -> sorted/indexed BAM.",
    workflow: {
      version: "0.1.0",
      app: "bionodulo",
      name: "BWA alignment skeleton",
      description: "Align reads to a reference and create a sorted BAM plus index.",
      nodes: [
        { id: "reference-1", type: "input_fasta", position: { x: 90, y: 90 }, params: { file: "reference.fa" } },
        { id: "reads-1", type: "input_fastq", position: { x: 90, y: 270 }, params: { files: ["data/sample_R1.fastq.gz", "data/sample_R2.fastq.gz"] } },
        { id: "bwa-mem-1", type: "bwa_mem", position: { x: 390, y: 190 }, params: { threads: 4 } },
        { id: "sort-1", type: "samtools_sort", position: { x: 680, y: 190 }, params: { threads: 4 } },
        { id: "index-1", type: "samtools_index", position: { x: 960, y: 190 }, params: {} },
      ],
      edges: [
        { id: "edge-ref-mem", from: { node: "reference-1", output: "fasta" }, to: { node: "bwa-mem-1", input: "reference" } },
        { id: "edge-reads-mem", from: { node: "reads-1", output: "reads" }, to: { node: "bwa-mem-1", input: "reads" } },
        { id: "edge-mem-sort", from: { node: "bwa-mem-1", output: "sam" }, to: { node: "sort-1", input: "alignment" } },
        { id: "edge-sort-index", from: { node: "sort-1", output: "bam" }, to: { node: "index-1", input: "bam" } },
      ],
      outputs: ["index-1"],
    },
  },
  {
    id: "command-prototype",
    name: "Command prototype",
    description: "A small utility template for wrapping one command and viewing its outputs.",
    workflow: {
      version: "0.1.0",
      app: "bionodulo",
      name: "Command prototype",
      description: "Prototype an external command before promoting it into a reusable node.",
      nodes: [
        { id: "command-1", type: "generic_command", position: { x: 180, y: 180 }, params: { command: "echo hello from BioNodulo" } },
      ],
      edges: [],
      outputs: ["command-1"],
    },
  },
];

function BioEdge(props) {
  const [edgePath] = getBezierPath(props);
  const midX = (props.sourceX + props.targetX) / 2;
  const midY = (props.sourceY + props.targetY) / 2;
  const color = props.style?.stroke || "#38bdf8";
  function openMenu(event) {
    event.preventDefault();
    event.stopPropagation();
    window.dispatchEvent(new CustomEvent("bionodulo:edge-menu", { detail: { edgeId: props.id, x: event.clientX, y: event.clientY } }));
  }
  return h(
    React.Fragment,
    null,
    h(BaseEdge, { path: edgePath, markerEnd: props.markerEnd, style: { strokeWidth: 2.7, ...props.style } }),
    h("path", { d: edgePath, className: "bio-edge-hitbox", "data-edge-id": props.id, onContextMenu: openMenu }),
    h("circle", { cx: midX, cy: midY, r: 5, className: "edge-menu-dot", style: { stroke: color }, "data-edge-id": props.id, onContextMenu: openMenu, onClick: (event) => event.stopPropagation() }),
  );
}

const edgeTypes = { bioEdge: BioEdge };

function BioNode({ id, data, selected }) {
  const meta = data.meta || {};
  const inputs = Object.entries({ ...(meta.inputs?.required || {}), ...(meta.inputs?.optional || {}) });
  const outputs = meta.outputs || [];
  const status = data.status || "idle";
  const ui = data.ui || {};
  const paramSummary = Object.entries(data.params || {})
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.length + " files" : value}`)
    .join(" / ");
  const rowCount = Math.max(inputs.length, outputs.length, 1);
  const nodeColor = ui.color;
  const nodeBgColor = ui.bgcolor;

  return h(
    "div",
    {
      className: `bio-node ${selected ? "selected" : ""} ${data.workflowOutput || meta.output_node ? "output-node" : ""} ${ui.pinned ? "is-pinned" : ""} ${ui.muted ? "is-muted" : ""} ${ui.bypassed ? "is-bypassed" : ""} status-${status}`,
      title: meta.description || data.type,
      style: nodeColor ? { borderTopColor: nodeColor, background: nodeBgColor || undefined } : undefined,
      onDoubleClick: (event) => {
        event.stopPropagation();
        window.dispatchEvent(new CustomEvent("bionodulo:edit-node", { detail: { nodeId: id } }));
      },
      onContextMenu: (event) => {
        event.preventDefault();
        event.stopPropagation();
        window.dispatchEvent(new CustomEvent("bionodulo:node-menu", { detail: { nodeId: id, x: event.clientX, y: event.clientY } }));
      },
    },
    h("div", { className: "node-title-row" },
      h("strong", null, meta.display_name || data.type),
      h("span", { className: "status-pill" }, ui.muted ? "muted" : ui.bypassed ? "bypass" : STATUS_LABELS[status] || status),
    ),
    h("div", { className: "node-type" }, data.workflowOutput ? `${data.type} / output` : data.type),
    data.previews?.length ? h("div", { className: "node-preview-chip", title: "Preview artifacts are available" }, `${data.previews.length} preview(s)`) : null,
    paramSummary ? h("div", { className: "node-params" }, paramSummary) : null,
    h(
      "div",
      { className: "socket-list" },
      Array.from({ length: rowCount }).map((_, index) => {
        const input = inputs[index];
        const output = outputs[index];
        return h("div", { key: `socket-row-${index}`, className: "socket-row" },
          h("span", { className: "socket-cell input-cell" },
            input ? h(React.Fragment, null,
              h(Handle, { type: "target", id: input[0], position: Position.Left, className: "socket-handle", title: `${input[0]}: ${input[1].type}` }),
              h("span", null, input[0]),
            ) : null,
          ),
          h("span", { className: "socket-cell output-cell" },
            output ? h(React.Fragment, null,
              h("span", null, output.name),
              h(Handle, { type: "source", id: output.name, position: Position.Right, className: "socket-handle", title: `${output.name}: ${output.type}` }),
            ) : null,
          ),
        );
      }),
    ),
  );
}

const GROUP_COLORS = ["#38bdf8", "#a78bfa", "#f59e0b", "#22c55e", "#fb7185", "#14b8a6", "#f97316", "#60a5fa"];
const NODE_COLORS = [
  { name: "red", title: "#6b2020", body: "#4a1515" },
  { name: "orange", title: "#6b3a10", body: "#4a2808" },
  { name: "yellow", title: "#6b5a10", body: "#4a3c08" },
  { name: "green", title: "#1a4a20", body: "#0f3014" },
  { name: "teal", title: "#104a4a", body: "#083030" },
  { name: "blue", title: "#103060", body: "#081840" },
  { name: "purple", title: "#3a1060", body: "#280840" },
  { name: "pink", title: "#601040", body: "#400828" },
  { name: "gray", title: "#3a3a3a", body: "#282828" },
];

function GroupNode({ id, data, selected }) {
  return h("div", {
    className: "bio-group-node",
    onContextMenu: (event) => {
      event.preventDefault();
      event.stopPropagation();
      window.dispatchEvent(new CustomEvent("bionodulo:group-menu", {
        detail: { groupId: data.groupId, x: event.clientX, y: event.clientY },
      }));
    },
  },
    h(NodeResizer, {
      isVisible: selected,
      minWidth: 180,
      minHeight: 100,
      lineClassName: "group-resize-line",
      handleClassName: "group-resize-handle",
      onResize: (_, params) => window.dispatchEvent(new CustomEvent("bionodulo:resize-group", { detail: { groupId: data.groupId, width: params.width, height: params.height } })),
    }),
    h("div", { className: "bio-group-header" },
      h("span", { className: "bio-group-title" }, data.label || "Group"),
    ),
  );
}

const nodeTypes = { bioNode: BioNode, group: GroupNode };

function App() {
  const [objectInfo, setObjectInfo] = useState({});
  const [nodes, setNodes, onNodesChangeBase] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [groups, setGroups] = useState([]);
  const [workflowTabs, setWorkflowTabs] = useState([{ id: "workflow-1", name: "FASTQ QC", ...EMPTY_WORKFLOW, environment: DEFAULT_ENVIRONMENT }]);
  const [activeTabId, setActiveTabId] = useState("workflow-1");
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState([]);
  const [paletteSearch, setPaletteSearch] = useState("");
  const [mockTools, setMockTools] = useState(true);
  const [environmentSpec, setEnvironmentSpec] = useState(DEFAULT_ENVIRONMENT);
  const [validation, setValidation] = useState({ valid: true, errors: [], warnings: [] });
  const [runs, setRuns] = useState([]);
  const [queue, setQueue] = useState({});
  const [logs, setLogs] = useState([]);
  const [currentRunId, setCurrentRunId] = useState(null);
  const [reactFlow, setReactFlow] = useState(null);
  const [paletteMenu, setPaletteMenu] = useState(null);
  const [canvasMenu, setCanvasMenu] = useState(null);
  const [groupMenu, setGroupMenu] = useState(null);
  const [nodeMenu, setNodeMenu] = useState(null);
  const [editingNodeId, setEditingNodeId] = useState(null);
  const [runPanelOpen, setRunPanelOpen] = useState(false);
  const [runPanelTab, setRunPanelTab] = useState("queue");
  const [runPanelWidth, setRunPanelWidth] = useState(380);
  const [edgeMenu, setEdgeMenu] = useState(null);
  const [dropActive, setDropActive] = useState(false);
  const [railPanel, setRailPanel] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [fileTree, setFileTree] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [workspaceRoot, setWorkspaceRootState] = useState("");
  const [workspaceDraft, setWorkspaceDraft] = useState("");
  const [directoryBrowser, setDirectoryBrowser] = useState(null);
  const [fileClipboard, setFileClipboard] = useState(null);
  const [showMiniMap, setShowMiniMap] = useState(false);
  const [linksHidden, setLinksHidden] = useState(false);
  const [viewportLocked, setViewportLocked] = useState(false);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [consoleHeight, setConsoleHeight] = useState(220);
  const [autoSaveMode, setAutoSaveMode] = useState("off");
  const [preserveView, setPreserveView] = useState(true);
  const [queueHistorySize, setQueueHistorySize] = useState(100);
  const [fileExplorerDepth, setFileExplorerDepth] = useState(4);
  const [showHiddenFiles, setShowHiddenFiles] = useState(false);
  const [strongHashing, setStrongHashing] = useState(false);
  const [tooltipsEnabled, setTooltipsEnabled] = useState(true);
  const [snapToGrid, setSnapToGrid] = useState(false);
  const [themePreference, setThemePreference] = useState(loadThemePreference);
  const [confirmFileDelete, setConfirmFileDelete] = useState(loadConfirmFileDelete);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiMessages, setAiMessages] = useState([{ role: "assistant", content: "Ask me to explain, debug, edit, or create a BioNodulo workflow. I can use the project docs and the active workflow as context." }]);
  const [aiBusy, setAiBusy] = useState(false);
  const [llmSettings, setLlmSettings] = useState(loadLlmSettings);
  const [zoomPercent, setZoomPercent] = useState(100);
  const [managerStatus, setManagerStatus] = useState(null);
  const [managerDiagnostics, setManagerDiagnostics] = useState(null);
  const [managerLoading, setManagerLoading] = useState(false);
  const [installRequest, setInstallRequest] = useState(null);
  const [installResult, setInstallResult] = useState(null);
  const [exportResult, setExportResult] = useState(null);
  const [envPanelInitialTab, setEnvPanelInitialTab] = useState("envs");
  const paletteSearchRef = useRef(null);
  const suppressTabPersistRef = useRef(false);
  const reconnectSuccessfulRef = useRef(true);
  const historyRef = useRef([]);
  const redoRef = useRef([]);
  const historyPausedRef = useRef(false);
  const nodeClipboardRef = useRef(null);

  useEffect(() => {
    if (suppressTabPersistRef.current) {
      suppressTabPersistRef.current = false;
      return;
    }
    setWorkflowTabs((tabs) => tabs.map((tab) => tab.id === activeTabId ? { ...tab, nodes, edges, groups, environment: environmentSpec } : tab));
  }, [nodes, edges, groups, environmentSpec, activeTabId]);

  useEffect(() => {
    persistLlmSettings(llmSettings);
  }, [llmSettings]);

  useEffect(() => {
    localStorage.setItem("bionodulo.theme", themePreference);
  }, [themePreference]);

  useEffect(() => {
    localStorage.setItem("bionodulo.confirm_file_delete", confirmFileDelete ? "1" : "0");
  }, [confirmFileDelete]);

  useEffect(() => {
    fetch("/object_info").then((res) => res.json()).then(setObjectInfo);
    fetchWorkspaceRoot();
    refreshRuns();
    refreshQueue();
  }, []);

  useEffect(() => {
    if (!nodes.length || !Object.keys(objectInfo).length) return;
    const timer = window.setTimeout(() => {
      refreshManagerStatus().catch(() => {});
    }, 450);
    return () => window.clearTimeout(timer);
  }, [nodes, edges, environmentSpec, mockTools, objectInfo]);

  useEffect(() => {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${location.host}/ws`);
    ws.onmessage = (message) => {
      const event = JSON.parse(message.data);
      if (event.type === "queue_updated") setQueue(event.data);
      if (event.type === "node_log") {
        setLogs((items) => [...items.slice(-500), event.data]);
      }
      if (event.type === "preview_available") {
        setRuns((items) => items.map((run) => run.run_id === event.data.run_id ? { ...run, previews: { ...(run.previews || {}), [event.data.node_id]: [...(run.previews?.[event.data.node_id] || []), event.data] } } : run));
        setNodes((items) => items.map((node) => node.id === event.data.node_id ? { ...node, data: { ...node.data, previews: [...(node.data.previews || []), event.data] } } : node));
      }
      if (["node_queued", "executing", "executed", "execution_cached", "execution_error", "execution_interrupted"].includes(event.type)) {
        const nodeId = event.data.node_id;
        const status =
          event.type === "node_queued" ? "queued" :
          event.type === "executing" ? "running" :
          event.type === "executed" ? "completed" :
          event.type === "execution_cached" ? "cached" :
          event.type === "execution_interrupted" ? "interrupted" :
          event.data.status || "failed";
        if (nodeId) setNodeStatus(nodeId, status);
        if (nodeId) {
          const line =
            event.type === "execution_error" ? event.data.message || status :
            event.type === "executed" ? "completed" :
            event.type === "execution_cached" ? "cache hit" :
            status;
          setLogs((items) => [...items.slice(-500), { run_id: event.data.run_id, node_id: nodeId, stream: "status", line }]);
        }
        refreshRuns();
      }
      if (event.type === "execution_success") refreshRuns();
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === "Escape") {
        setPaletteMenu(null);
        setCanvasMenu(null);
        setGroupMenu(null);
        setNodeMenu(null);
        setEdgeMenu(null);
        setEditingNodeId(null);
        setRailPanel(null);
        setSettingsOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    function onEditNode(event) {
      setEditingNodeId(event.detail.nodeId);
      setNodeMenu(null);
      setPaletteMenu(null);
      setCanvasMenu(null);
    }
    function onNodeMenu(event) {
      setPaletteMenu(null);
      setCanvasMenu(null);
      setGroupMenu(null);
      setSelection([event.detail.nodeId]);
      setNodeMenu({ x: event.detail.x, y: event.detail.y, nodeId: event.detail.nodeId });
    }
    function onGroupMenu(event) {
      setPaletteMenu(null);
      setCanvasMenu(null);
      setNodeMenu(null);
      setEdgeMenu(null);
      setGroupMenu({ x: event.detail.x, y: event.detail.y, groupId: event.detail.groupId });
    }
    function onEdgeMenu(event) {
      setPaletteMenu(null);
      setCanvasMenu(null);
      setGroupMenu(null);
      setNodeMenu(null);
      setSelectedNodeId(null);
      setEdgeMenu({ x: event.detail.x, y: event.detail.y, edgeId: event.detail.edgeId });
    }
  function onNativeEdgeContext(event) {
      const target = event.target?.closest?.(".edge-menu-dot, .bio-edge-hitbox");
      if (!target) return;
      event.preventDefault();
      event.stopPropagation();
      setPaletteMenu(null);
      setCanvasMenu(null);
      setGroupMenu(null);
      setNodeMenu(null);
      setSelectedNodeId(null);
      setEdgeMenu({ x: event.clientX, y: event.clientY, edgeId: target.dataset.edgeId });
    }
    function onToggleGroup(event) {
      toggleGroupCollapsed(event.detail.groupId);
    }
    function onResizeGroup(event) {
      resizeGroup(event.detail.groupId, event.detail);
    }
    function onDeleteGroup(event) {
      deleteGroup(event.detail.groupId);
    }
    window.addEventListener("bionodulo:edit-node", onEditNode);
    window.addEventListener("bionodulo:node-menu", onNodeMenu);
    window.addEventListener("bionodulo:group-menu", onGroupMenu);
    window.addEventListener("bionodulo:edge-menu", onEdgeMenu);
    window.addEventListener("bionodulo:toggle-group", onToggleGroup);
    window.addEventListener("bionodulo:resize-group", onResizeGroup);
    window.addEventListener("bionodulo:delete-group", onDeleteGroup);
    document.addEventListener("contextmenu", onNativeEdgeContext, true);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("bionodulo:edit-node", onEditNode);
      window.removeEventListener("bionodulo:node-menu", onNodeMenu);
      window.removeEventListener("bionodulo:group-menu", onGroupMenu);
      window.removeEventListener("bionodulo:edge-menu", onEdgeMenu);
      window.removeEventListener("bionodulo:toggle-group", onToggleGroup);
      window.removeEventListener("bionodulo:resize-group", onResizeGroup);
      window.removeEventListener("bionodulo:delete-group", onDeleteGroup);
      document.removeEventListener("contextmenu", onNativeEdgeContext, true);
    };
  }, []);

  useEffect(() => {
    if (paletteMenu) {
      setTimeout(() => paletteSearchRef.current?.focus(), 0);
    }
  }, [paletteMenu]);

  useEffect(() => {
    function onShortcut(event) {
      const target = event.target?.tagName?.toLowerCase?.();
      const typing = ["input", "textarea", "select"].includes(target);
      if (typing) return;
      const key = event.key.toLowerCase();
      if ((event.ctrlKey || event.metaKey) && key === "z") {
        event.preventDefault();
        event.shiftKey ? redoCanvas() : undoCanvas();
      } else if ((event.ctrlKey || event.metaKey) && key === "y") {
        event.preventDefault();
        redoCanvas();
      } else if ((event.ctrlKey || event.metaKey) && key === "g") {
        event.preventDefault();
        groupSelectedNodes();
      } else if ((event.ctrlKey || event.metaKey) && key === "a") {
        event.preventDefault();
        setSelection(nodes.map((node) => node.id));
      } else if ((event.ctrlKey || event.metaKey) && key === "c") {
        event.preventDefault();
        copySelectedNodes();
      } else if ((event.ctrlKey || event.metaKey) && key === "v") {
        event.preventDefault();
        pasteCopiedNodes();
      } else if ((event.ctrlKey || event.metaKey) && key === "f") {
        event.preventDefault();
        openPalette({ preventDefault() {}, clientX: window.innerWidth / 2, clientY: window.innerHeight / 2 });
      } else if (key === "delete" || key === "backspace") {
        if (selectedNodeIds.length) {
          event.preventDefault();
          deleteSelectedNodes();
        }
      } else if (key === "r" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        runWorkflow(false);
      }
    }
    window.addEventListener("keydown", onShortcut);
    return () => window.removeEventListener("keydown", onShortcut);
  }, [nodes, edges, groups, selectedNodeId, selectedNodeIds, paletteMenu, mockTools]);

  const editingNode = nodes.find((node) => node.id === editingNodeId);
  const selectedNodes = useMemo(() => nodes.filter((node) => selectedNodeIds.includes(node.id) || node.selected), [nodes, selectedNodeIds]);
  const paletteNodes = useMemo(() => filterNodes(Object.values(objectInfo), paletteSearch), [objectInfo, paletteSearch]);
  const commonNodes = useMemo(() => COMMON_NODE_IDS.map((id) => objectInfo[id]).filter(Boolean), [objectInfo]);
  const groupedNodes = useMemo(() => groupNodesByCategory(Object.values(objectInfo)), [objectInfo]);
  const coloredEdges = useMemo(() => {
    return edges.map((edge) => {
      const color = edgeColorForSource(edge.source, edge.sourceHandle);
      return { ...edge, style: { ...(edge.style || {}), stroke: color, strokeWidth: 2.7 }, data: { ...(edge.data || {}), color } };
    });
  }, [edges]);
  const collapsedGroupIds = useMemo(() => new Set(groups.filter((group) => group.collapsed).map((group) => group.id)), [groups]);
  const hiddenNodeIds = useMemo(() => new Set(nodes.filter((node) => collapsedGroupIds.has(node.data?.ui?.group_id)).map((node) => node.id)), [nodes, collapsedGroupIds]);
  const displayEdges = useMemo(() => {
    const withGroupHiding = coloredEdges.map((edge) => ({ ...edge, hidden: linksHidden || hiddenNodeIds.has(edge.source) || hiddenNodeIds.has(edge.target) }));
    return withGroupHiding;
  }, [coloredEdges, linksHidden, hiddenNodeIds]);
  const displayNodes = useMemo(() => [
    ...groups.map((group) => ({
      id: `group:${group.id}`,
      type: "group",
      position: group.position || { x: 0, y: 0 },
      selectable: true,
      draggable: true,
      zIndex: 0,
      style: {
        width: group.width || 360,
        height: group.height || 240,
        border: `2px solid ${group.color || "#38bdf8"}`,
        background: "color-mix(in srgb, var(--surface) 72%, transparent)",
        borderRadius: 8,
        color: "var(--muted)",
        fontWeight: 800,
        padding: 8,
      },
      data: { label: group.name || "Group", groupId: group.id, collapsed: Boolean(group.collapsed) },
    })),
    ...nodes.map((node) => ({ ...node, hidden: hiddenNodeIds.has(node.id), zIndex: 1, draggable: !node.data?.ui?.pinned })),
  ], [nodes, groups, hiddenNodeIds]);

  function snapshotCanvas() {
    return { nodes, edges, groups };
  }

  function restoreCanvas(snapshot) {
    if (!snapshot) return;
    historyPausedRef.current = true;
    setNodes(snapshot.nodes || []);
    setEdges(snapshot.edges || []);
    setGroups(snapshot.groups || []);
    window.setTimeout(() => { historyPausedRef.current = false; }, 0);
  }

  function recordHistory() {
    if (historyPausedRef.current) return;
    historyRef.current = [...historyRef.current.slice(-40), snapshotCanvas()];
    redoRef.current = [];
  }

  function undoCanvas() {
    const previous = historyRef.current.pop();
    if (!previous) return;
    redoRef.current = [...redoRef.current.slice(-40), snapshotCanvas()];
    restoreCanvas(previous);
  }

  function redoCanvas() {
    const next = redoRef.current.pop();
    if (!next) return;
    historyRef.current = [...historyRef.current.slice(-40), snapshotCanvas()];
    restoreCanvas(next);
  }

  function handleNodesChange(changes) {
    const groupChanges = changes.filter((change) => String(change.id || "").startsWith("group:"));
    if (groupChanges.length) {
      if (groupChanges.some((change) => change.type !== "select")) recordHistory();
      let groupDx = 0, groupDy = 0, movedGroupId = null;
      setGroups((items) => {
        const updated = items.map((group) => {
          const change = groupChanges.find((item) => item.id === `group:${group.id}`);
          if (!change) return group;
          if (change.type === "position" && change.position) {
            groupDx = change.position.x - (group.position?.x || 0);
            groupDy = change.position.y - (group.position?.y || 0);
            movedGroupId = group.id;
            return { ...group, position: change.position };
          }
          if (change.type === "dimensions" && change.dimensions) return { ...group, width: change.dimensions.width || group.width, height: change.dimensions.height || group.height };
          return group;
        });
        if (groupDx !== 0 || groupDy !== 0) {
          setNodes((nodeItems) => nodeItems.map((node) =>
            node.data?.ui?.group_id === movedGroupId
              ? { ...node, position: { x: node.position.x + groupDx, y: node.position.y + groupDy } }
              : node
          ));
        }
        return updated;
      });
    }
    const realChanges = changes.filter((change) => !String(change.id || "").startsWith("group:"));
    if (realChanges.some((change) => change.type !== "select")) recordHistory();
    const selectionChanges = realChanges.filter((change) => change.type === "select");
    if (selectionChanges.length) {
      const next = new Set(selectedNodeIds);
      for (const change of selectionChanges) {
        if (change.selected) next.add(change.id);
        else next.delete(change.id);
      }
      const ids = [...next].filter((id) => nodes.some((node) => node.id === id));
      setSelectedNodeIds(ids);
      setSelectedNodeId(ids.at(-1) || null);
    }
    onNodesChangeBase(realChanges);
  }

  function setSelection(ids) {
    const clean = [...new Set(ids)].filter((id) => nodes.some((node) => node.id === id));
    setSelectedNodeIds(clean);
    setSelectedNodeId(clean.at(-1) || null);
    setNodes((items) => items.map((node) => ({ ...node, selected: clean.includes(node.id) })));
  }

  function clearSelection() {
    setSelectedNodeIds([]);
    setSelectedNodeId(null);
    setNodes((items) => items.map((node) => node.selected ? { ...node, selected: false } : node));
  }

  function handleNodeClick(event, node) {
    if (event.ctrlKey || event.metaKey) {
      const next = selectedNodeIds.includes(node.id) ? selectedNodeIds.filter((id) => id !== node.id) : [...selectedNodeIds, node.id];
      setSelection(next);
      return;
    }
    if (event.shiftKey && selectedNodeIds.length) {
      setSelection([...selectedNodeIds, node.id]);
      return;
    }
    setSelection([node.id]);
  }
  const paletteGroups = useMemo(() => groupNodesByCategory(paletteNodes), [paletteNodes]);

  const onConnect = useCallback((connection) => {
    setEdges((existing) => addEdge({ ...connection, id: `edge-${Date.now()}`, type: "bioEdge" }, existing));
  }, [setEdges]);

  const onReconnectStart = useCallback(() => {
    reconnectSuccessfulRef.current = false;
  }, []);

  const onReconnect = useCallback((oldEdge, newConnection) => {
    reconnectSuccessfulRef.current = true;
    setEdges((existing) => reconnectEdge(oldEdge, newConnection, existing));
  }, [setEdges]);

  const onReconnectEnd = useCallback((_, edge) => {
    if (!reconnectSuccessfulRef.current) {
      setEdges((existing) => existing.filter((item) => item.id !== edge.id));
    }
    reconnectSuccessfulRef.current = true;
  }, [setEdges]);

  function setNodeStatus(nodeId, status) {
    setNodes((items) => items.map((node) => node.id === nodeId ? { ...node, data: { ...node.data, status } } : node));
  }

  function addNode(meta, position = null) {
    recordHistory();
    const id = `${meta.id}-${Date.now().toString().slice(-5)}`;
    const params = defaultsFor(meta);
    setNodes((items) => [
      ...items.map((node) => ({ ...node, selected: false })),
      {
        id,
        type: "bioNode",
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        initialWidth: NODE_WIDTH,
        initialHeight: NODE_HEIGHT,
        selected: true,
        position: position || { x: 120 + items.length * 40, y: 120 + items.length * 30 },
        data: { type: meta.id, meta, params, ui: {}, status: "idle", workflowOutput: Boolean(meta.output_node) },
      },
    ]);
    setSelectedNodeId(id);
    setSelectedNodeIds([id]);
    setPaletteMenu(null);
  }

  function duplicateNode(nodeId) {
    const original = nodes.find((node) => node.id === nodeId);
    if (!original) return;
    recordHistory();
    const id = `${original.data.type}-${Date.now().toString().slice(-5)}`;
    setNodes((items) => [
      ...items.map((node) => ({ ...node, selected: false })),
      {
        ...original,
        id,
        selected: false,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        initialWidth: NODE_WIDTH,
        initialHeight: NODE_HEIGHT,
        position: { x: original.position.x + 40, y: original.position.y + 40 },
        data: { ...original.data, params: { ...(original.data.params || {}) }, status: "idle" },
      },
    ]);
    setSelectedNodeId(id);
    setSelectedNodeIds([id]);
    setNodeMenu(null);
  }

  function deleteNode(nodeId) {
    deleteNodes([nodeId]);
  }

  function deleteSelectedNodes() {
    deleteNodes(selectedNodeIds);
  }

  function deleteNodes(nodeIds) {
    const remove = new Set(nodeIds);
    if (!remove.size) return;
    recordHistory();
    setNodes((items) => items.filter((node) => !remove.has(node.id)));
    setEdges((items) => items.filter((edge) => !remove.has(edge.source) && !remove.has(edge.target)));
    setSelectedNodeIds((ids) => ids.filter((id) => !remove.has(id)));
    if (selectedNodeId && remove.has(selectedNodeId)) setSelectedNodeId(null);
    if (editingNodeId && remove.has(editingNodeId)) setEditingNodeId(null);
    setNodeMenu(null);
  }

  function toggleWorkflowOutput(nodeId) {
    recordHistory();
    setNodes((items) => items.map((node) => node.id === nodeId ? { ...node, data: { ...node.data, workflowOutput: !node.data.workflowOutput } } : node));
    setNodeMenu(null);
  }

  function updateNodeUi(nodeId, patch) {
    updateNodesUi([nodeId], patch);
  }

  function updateSelectedNodesUi(patch) {
    updateNodesUi(selectedNodeIds.length ? selectedNodeIds : selectedNodeId ? [selectedNodeId] : [], patch);
  }

  function updateNodesUi(nodeIds, patch) {
    const ids = new Set(nodeIds);
    if (!ids.size) return;
    recordHistory();
    setNodes((items) => items.map((node) => ids.has(node.id) ? { ...node, data: { ...node.data, ui: { ...(node.data.ui || {}), ...patch } } } : node));
    setNodeMenu(null);
  }

  function setNodeColor(nodeId, color) {
    recordHistory();
    setNodes((items) => items.map((node) => {
      if (node.id !== nodeId) return node;
      if (!color) {
        return { ...node, data: { ...node.data, ui: { ...(node.data.ui || {}), color: null, bgcolor: null } } };
      }
      return { ...node, data: { ...node.data, ui: { ...(node.data.ui || {}), color: color.title, bgcolor: color.body } } };
    }));
  }

  function groupSelectedNodes() {
    const selected = selectedNodes.length ? selectedNodes : nodes.filter((node) => node.id === selectedNodeId);
    if (!selected.length) return;
    recordHistory();
    const minX = Math.min(...selected.map((node) => node.position.x)) - 32;
    const minY = Math.min(...selected.map((node) => node.position.y)) - 52;
    const maxX = Math.max(...selected.map((node) => node.position.x + NODE_WIDTH)) + 32;
    const maxY = Math.max(...selected.map((node) => node.position.y + NODE_HEIGHT)) + 32;
    const id = `group-${Date.now().toString().slice(-5)}`;
    setGroups((items) => [...items, { id, name: "Group", position: { x: minX, y: minY }, width: maxX - minX, height: maxY - minY, color: EDGE_PALETTE[items.length % EDGE_PALETTE.length], collapsed: false }]);
    setNodes((items) => items.map((node) => selected.some((item) => item.id === node.id) ? { ...node, data: { ...node.data, ui: { ...(node.data.ui || {}), group_id: id } } } : node));
  }

  function toggleGroupCollapsed(groupId) {
    recordHistory();
    setGroups((items) => items.map((group) => group.id === groupId ? { ...group, collapsed: !group.collapsed } : group));
  }

  function resizeGroup(groupId, patch) {
    setGroups((items) => items.map((group) => group.id === groupId ? { ...group, width: patch.width || group.width, height: patch.height || group.height } : group));
  }

  function deleteGroup(groupId) {
    recordHistory();
    setGroups((items) => items.filter((group) => group.id !== groupId));
    setNodes((items) => items.map((node) => node.data?.ui?.group_id === groupId ? { ...node, data: { ...node.data, ui: { ...(node.data.ui || {}), group_id: null } } } : node));
  }

  function renameGroup(groupId, name) {
    recordHistory();
    setGroups((items) => items.map((group) => group.id === groupId ? { ...group, name } : group));
  }

  function setGroupColor(groupId, color) {
    recordHistory();
    setGroups((items) => items.map((group) => group.id === groupId ? { ...group, color } : group));
  }

  function copySelectedNodes() {
    const selected = selectedNodes.length ? selectedNodes : nodes.filter((node) => node.id === selectedNodeId);
    if (!selected.length) return;
    const ids = new Set(selected.map((node) => node.id));
    nodeClipboardRef.current = {
      nodes: selected.map((node) => ({ ...node, selected: false })),
      edges: edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)),
    };
  }

  function pasteCopiedNodes(position = null) {
    const clip = nodeClipboardRef.current;
    if (!clip?.nodes?.length) return;
    recordHistory();
    const stamp = Date.now().toString().slice(-5);
    const idMap = new Map(clip.nodes.map((node, index) => [node.id, `${node.data.type}-${stamp}-${index + 1}`]));
    const minX = Math.min(...clip.nodes.map((node) => node.position.x));
    const minY = Math.min(...clip.nodes.map((node) => node.position.y));
    const offset = position ? { x: position.x - minX, y: position.y - minY } : { x: 48, y: 48 };
    const pastedNodes = clip.nodes.map((node) => ({
      ...node,
      id: idMap.get(node.id),
      selected: true,
      position: { x: node.position.x + offset.x, y: node.position.y + offset.y },
      data: { ...node.data, params: { ...(node.data.params || {}) }, status: "idle" },
    }));
    const pastedEdges = (clip.edges || []).map((edge, index) => ({
      ...edge,
      id: `edge-${stamp}-${index + 1}`,
      source: idMap.get(edge.source),
      target: idMap.get(edge.target),
    }));
    setNodes((items) => [...items.map((node) => ({ ...node, selected: false })), ...pastedNodes]);
    setEdges((items) => [...items, ...pastedEdges]);
    setSelectedNodeIds(pastedNodes.map((node) => node.id));
    setSelectedNodeId(pastedNodes.at(-1)?.id || null);
  }

  function updateNodeParams(nodeId, name, value, spec) {
    recordHistory();
    setNodes((items) => items.map((node) => {
      if (node.id !== nodeId) return node;
      return { ...node, data: { ...node.data, params: { ...(node.data.params || {}), [name]: parseParamValue(value, spec) } } };
    }));
  }

  function defaultsFor(meta) {
    const result = {};
    for (const group of ["required", "optional"]) {
      for (const [name, spec] of Object.entries(meta.inputs?.[group] || {})) {
        if (Object.prototype.hasOwnProperty.call(spec, "default")) result[name] = spec.default;
      }
    }
    return result;
  }

  function workflowFromCanvas() {
    const workflowNodes = nodes.map((node) => ({
      id: node.id,
      type: node.data.type,
      position: node.position,
      params: node.data.params || {},
      node_info: nodeInfoForWorkflow(node),
      ui: node.data.ui || {},
    }));
    return {
      version: "0.1.0",
      app: "bionodulo",
      name: "FASTQ QC pipeline",
      description: "Visual bioinformatics workflow created in BioNodulo.",
      nodes: workflowNodes,
      edges: edges.map((edge) => ({
        id: edge.id,
        from: { node: edge.source, output: edge.sourceHandle },
        to: { node: edge.target, input: edge.targetHandle },
      })),
      groups,
      outputs: nodes.filter((node) => node.data.workflowOutput || node.data.meta?.output_node).map((node) => node.id),
      environment: environmentSpec,
      dependencies: workflowDependencies(workflowNodes, environmentSpec),
    };
  }

  function loadWorkflow(workflow, nameHint = null) {
    recordHistory();
    const outputSet = new Set(workflow.outputs || []);
    const workflowGroups = workflow.groups || [];
    setEnvironmentSpec(normalizeEnvironment(workflow.environment));
    const nextNodes = workflow.nodes.map((node) => {
      const meta = objectInfo[node.type] || { id: node.type, display_name: node.type };
      return {
        id: node.id,
        type: "bioNode",
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        initialWidth: NODE_WIDTH,
        initialHeight: NODE_HEIGHT,
        position: node.position || { x: 0, y: 0 },
        data: { type: node.type, meta, params: node.params || {}, ui: node.ui || {}, status: "idle", workflowOutput: outputSet.has(node.id) || Boolean(meta.output_node) },
      };
    });
    const nextEdges = workflow.edges.map((edge) => {
      const from = edgeFrom(edge);
      const to = edgeTo(edge);
      return {
        id: edge.id,
        type: "bioEdge",
        source: from.node,
        sourceHandle: from.output,
        target: to.node,
        targetHandle: to.input,
      };
    });
    setNodes(nextNodes);
    setEdges(nextEdges);
    setGroups(workflowGroups);
    setWorkflowTabs((tabs) => tabs.map((tab) => tab.id === activeTabId ? { ...tab, name: workflow.name || nameHint || tab.name, nodes: nextNodes, edges: nextEdges, groups: workflowGroups, environment: normalizeEnvironment(workflow.environment) } : tab));
    setSelectedNodeId(nextNodes[0]?.id || null);
    setSelectedNodeIds(nextNodes[0]?.id ? [nextNodes[0].id] : []);
    setLogs([]);
    setPaletteMenu(null);
    setNodeMenu(null);
    setEdgeMenu(null);
    setTimeout(() => reactFlow?.fitView?.({ padding: 0.18, duration: 300 }), 0);
  }

  async function validate() {
    const result = await fetch("/workflow/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow: workflowFromCanvas(), mock_tools: mockTools }),
    }).then((res) => res.json());
    setValidation(result);
    const invalid = new Set((result.errors || []).map((issue) => issue.node_id).filter(Boolean));
    setNodes((items) => items.map((node) => ({ ...node, data: { ...node.data, status: invalid.has(node.id) ? "invalid" : node.data.status === "invalid" ? "idle" : node.data.status } })));
    return result;
  }

  async function runWorkflow(force = false, forceNodes = []) {
    const result = await validate();
    if (!result.valid) return;
    setLogs([]);
    setNodes((items) => items.map((node) => ({ ...node, data: { ...node.data, status: "idle" } })));
    const run = await fetch("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow: workflowFromCanvas(), mock_tools: mockTools, force, force_nodes: forceNodes, options: { reuse_cache: true, strong_hashing: strongHashing, stop_on_error: true } }),
    }).then((res) => res.json());
    setCurrentRunId(run.run_id);
    refreshRuns();
    setNodeMenu(null);
  }

  async function stopRun() {
    if (!currentRunId) return;
    await fetch(`/runs/${currentRunId}/interrupt`, { method: "POST" });
  }

  async function refreshRuns() {
    setRuns(await fetch("/runs").then((res) => res.json()).catch(() => []));
  }

  async function refreshQueue() {
    setQueue(await fetch("/queue").then((res) => res.json()).catch(() => ({})));
  }

  async function clearQueue() {
    await fetch("/queue/clear", { method: "POST" });
    refreshQueue();
  }

  async function loadRunSnapshot(runId) {
    const run = await fetch(`/runs/${runId}`).then((res) => res.json());
    if (!run.run_dir) return;
    const path = `${run.run_dir.replace(/\\/g, "/").split("/").slice(-1)[0]}/workflow.json`;
    const snapshot = await fetch(`/workspace/file?${new URLSearchParams({ path: `runs/${path}` })}`).then((res) => res.json());
    loadWorkflow(JSON.parse(snapshot.content), run.workflow_name || runId);
  }

  async function refreshManagerStatus() {
    setManagerLoading(true);
    try {
      setManagerStatus(await fetch("/manager/status").then((res) => res.json()));
      setManagerDiagnostics(await fetch("/manager/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow: workflowFromCanvas(), mock_tools: mockTools }),
      }).then((res) => res.json()));
    } finally {
      setManagerLoading(false);
    }
  }

  async function installPlans(plans) {
    const targets = (plans || []).map((plan) => plan.target || plan.action).filter(Boolean);
    const result = await fetch("/manager/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow: workflowFromCanvas(), targets }),
    }).then((res) => res.json());
    setInstallResult(result);
    await refreshManagerStatus();
  }

  async function exportActiveWorkflow(format = "snakemake") {
    const response = await fetch("/workflow/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow: workflowFromCanvas(), format }),
    });
    const result = await response.json();
    setExportResult(result);
  }

  async function sendAIMessage(content) {
    const trimmed = content.trim();
    if (!trimmed || aiBusy) return;
    const userMessage = { id: `user-${Date.now()}`, role: "user", content: trimmed };
    const assistantId = `assistant-${Date.now()}`;
    const nextMessages = [...aiMessages, userMessage];
    const baselineWorkflow = workflowFromCanvas();
    setAiMessages([...nextMessages, { id: assistantId, role: "assistant", content: "", streaming: true }]);
    setAiBusy(true);
    try {
      const response = await fetch("/ai/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow: baselineWorkflow,
          messages: nextMessages.filter((message) => message.role !== "assistant" || message.content !== aiMessages[0]?.content).slice(-12),
          settings: llmSettings,
        }),
      });
      if (!response.body) throw new Error("Streaming is not available in this browser.");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamedText = "";
      let finalResponse = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.type === "token") {
            streamedText += event.text || "";
            setAiMessages((items) => items.map((message) => message.id === assistantId ? { ...message, content: streamedText, streaming: true } : message));
          }
          if (event.type === "final") finalResponse = event.data;
        }
      }
      setAiMessages((items) => items.map((message) => message.id === assistantId ? {
        ...message,
        content: streamedText || finalResponse?.reply || "No response returned.",
        streaming: false,
        workflow: finalResponse?.workflow && finalResponse?.validation?.valid !== false ? finalResponse.workflow : null,
        baselineWorkflow,
        nodeBlueprint: finalResponse?.node_blueprint || null,
      } : message));
      if (finalResponse?.validation && finalResponse.validation.valid === false) setValidation(finalResponse.validation);
    } catch (error) {
      setAiMessages((items) => items.map((message) => message.id === assistantId ? { ...message, content: `AI request failed: ${error.message}`, streaming: false } : message));
    } finally {
      setAiBusy(false);
    }
  }

  function updateLlmSettings(patch) {
    setLlmSettings((current) => ({ ...current, ...patch }));
  }

  function flowPositionFromEvent(event) {
    return reactFlow?.screenToFlowPosition
      ? reactFlow.screenToFlowPosition({ x: event.clientX, y: event.clientY })
      : { x: event.clientX, y: event.clientY };
  }

  function openPalette(event) {
    event.preventDefault();
    setNodeMenu(null);
    setGroupMenu(null);
    setEdgeMenu(null);
    setRailPanel(null);
    setPaletteSearch("");
    setPaletteMenu({ x: event.clientX, y: event.clientY, flowPosition: flowPositionFromEvent(event) });
  }

  function openCanvasMenu(event) {
    event.preventDefault();
    setNodeMenu(null);
    setGroupMenu(null);
    setEdgeMenu(null);
    setPaletteMenu(null);
    setRailPanel(null);
    setCanvasMenu({ x: event.clientX, y: event.clientY, flowPosition: flowPositionFromEvent(event), addOpen: false });
  }

  function openAddNodeFromCanvasMenu() {
    setCanvasMenu((current) => current ? { ...current, addOpen: !current.addOpen } : current);
  }

  function addNodeFromCanvasMenu(meta) {
    addNode(meta, canvasMenu?.flowPosition || null);
    setCanvasMenu(null);
  }

  function pasteAt(position = null) {
    pasteCopiedNodes(position);
    setCanvasMenu(null);
  }

  function createGroupAt(position = null) {
    recordHistory();
    const id = `group-${Date.now().toString().slice(-5)}`;
    setGroups((items) => [...items, {
      id,
      name: "Group",
      position: position || { x: 80, y: 80 },
      width: 420,
      height: 260,
      color: EDGE_PALETTE[items.length % EDGE_PALETTE.length],
      collapsed: false,
    }]);
    setCanvasMenu(null);
  }

  function openNodeMenu(event, node) {
    event.preventDefault();
    event.stopPropagation();
    setPaletteMenu(null);
    setCanvasMenu(null);
    setGroupMenu(null);
    setSelection([node.id]);
    setNodeMenu({ x: event.clientX, y: event.clientY, nodeId: node.id });
  }

  function openEdgeMenu(event, edge) {
    event.preventDefault();
    event.stopPropagation();
    setPaletteMenu(null);
    setCanvasMenu(null);
    setGroupMenu(null);
    setNodeMenu(null);
    setSelectedNodeId(null);
    setSelectedNodeIds([]);
    setEdgeMenu({ x: event.clientX, y: event.clientY, edgeId: edge.id });
  }

  function deleteEdge(edgeId) {
    setEdges((items) => items.filter((edge) => edge.id !== edgeId));
    setEdgeMenu(null);
  }

  function startRunPanelResize(event) {
    event.preventDefault();
    const move = (moveEvent) => {
      setRunPanelWidth(clamp(window.innerWidth - moveEvent.clientX, 280, 560));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      document.body.classList.remove("is-resizing-x");
    };
    document.body.classList.add("is-resizing-x");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function switchWorkflowTab(tabId) {
    const tab = workflowTabs.find((item) => item.id === tabId);
    if (!tab) return;
    suppressTabPersistRef.current = true;
    setActiveTabId(tabId);
    setNodes(tab.nodes || []);
    setEdges(tab.edges || []);
    setGroups(tab.groups || []);
    setEnvironmentSpec(normalizeEnvironment(tab.environment));
    setSelectedNodeId(null);
    setSelectedNodeIds([]);
    setPaletteMenu(null);
    setNodeMenu(null);
    setEdgeMenu(null);
  }

  function addWorkflowTab() {
    const id = `workflow-${Date.now().toString().slice(-6)}`;
    const tab = { id, name: `Workflow ${workflowTabs.length + 1}`, nodes: [], edges: [], groups: [], environment: DEFAULT_ENVIRONMENT };
    setWorkflowTabs((tabs) => [...tabs, tab]);
    suppressTabPersistRef.current = true;
    setActiveTabId(id);
    setNodes([]);
    setEdges([]);
    setGroups([]);
    setEnvironmentSpec(DEFAULT_ENVIRONMENT);
    setSelectedNodeId(null);
  }

  function closeWorkflowTab(tabId, event) {
    event.stopPropagation();
    if (workflowTabs.length === 1) {
      setNodes([]);
      setEdges([]);
      setWorkflowTabs([{ id: "workflow-1", name: "Workflow 1", nodes: [], edges: [], groups: [], environment: DEFAULT_ENVIRONMENT }]);
      setActiveTabId("workflow-1");
      setEnvironmentSpec(DEFAULT_ENVIRONMENT);
      setGroups([]);
      setSelectedNodeIds([]);
      return;
    }
    const closingIndex = workflowTabs.findIndex((tab) => tab.id === tabId);
    const remaining = workflowTabs.filter((tab) => tab.id !== tabId);
    setWorkflowTabs(remaining);
    if (tabId === activeTabId) {
      const nextTab = remaining[Math.max(0, closingIndex - 1)];
      suppressTabPersistRef.current = true;
      setActiveTabId(nextTab.id);
      setNodes(nextTab.nodes || []);
      setEdges(nextTab.edges || []);
      setGroups(nextTab.groups || []);
      setEnvironmentSpec(normalizeEnvironment(nextTab.environment));
      setSelectedNodeIds([]);
    }
  }

  async function loadDroppedWorkflow(file) {
    if (!file) {
      setValidation({
        valid: false,
        errors: [{ level: "error", code: "unsupported_drop", message: "Drop a workflow JSON or output file with embedded BioNodulo metadata." }],
        warnings: [],
      });
      return;
    }
    try {
      const text = await file.text();
      const workflow = file.name.toLowerCase().endsWith(".json")
        ? JSON.parse(text)
        : (await fetch("/workflow/extract", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: file.name, content: text }),
          }).then((res) => res.json())).workflow;
      loadWorkflow(workflow, file.name.replace(/\.json$/i, ""));
      setValidation({ valid: true, errors: [], warnings: [] });
    } catch (error) {
      setValidation({
        valid: false,
        errors: [{ level: "error", code: "bad_workflow_drop", message: `Could not load embedded workflow: ${error.message}` }],
        warnings: [],
      });
    }
  }

  function handleDragOver(event) {
    const types = [...(event.dataTransfer?.types || [])];
    const hasFile = [...(event.dataTransfer?.items || [])].some((item) => item.kind === "file");
    if (hasFile || types.includes("application/bionodulo-workspace-file")) {
      event.preventDefault();
      setDropActive(true);
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    setDropActive(false);
    const workspaceFile = event.dataTransfer?.getData("application/bionodulo-workspace-file");
    if (workspaceFile) {
      try {
        const item = JSON.parse(workspaceFile);
        if (item.name?.toLowerCase?.().endsWith(".json")) loadWorkspaceWorkflow(item);
      } catch (error) {
        setValidation({ valid: false, errors: [{ level: "error", code: "workspace_drop", message: `Could not import workspace item: ${error.message}` }], warnings: [] });
      }
      return;
    }
    loadDroppedWorkflow(event.dataTransfer?.files?.[0]);
  }

  async function refreshFileTree() {
    setFileLoading(true);
    try {
      const query = new URLSearchParams({ depth: String(fileExplorerDepth), show_hidden: showHiddenFiles ? "1" : "0" });
      const tree = await fetch(`/workspace/files?${query}`).then((res) => res.json());
      setFileTree(tree);
      if (tree.absolute_path) {
        setWorkspaceRootState(tree.absolute_path);
        setWorkspaceDraft(tree.absolute_path);
      }
    } catch (error) {
      setFileTree({ name: "Workspace", type: "directory", path: ".", children: [{ name: error.message, path: "", type: "file", size: 0 }] });
    } finally {
      setFileLoading(false);
    }
  }

  async function fetchWorkspaceRoot() {
    const root = await fetch("/workspace/root").then((res) => res.json()).catch(() => null);
    if (root?.path) {
      setWorkspaceRootState(root.path);
      setWorkspaceDraft(root.path);
    }
  }

  async function applyWorkspaceRoot(path = workspaceDraft) {
    const trimmed = String(path || "").trim();
    if (!trimmed) return;
    const response = await fetch("/workspace/root", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: trimmed }),
    });
    const result = await response.json();
    if (!response.ok) {
      setValidation({ valid: false, errors: [{ level: "error", code: "workspace_root", message: result.detail || "Could not switch workspace." }], warnings: [] });
      return;
    }
    setWorkspaceRootState(result.path);
    setWorkspaceDraft(result.path);
    setDirectoryBrowser(null);
    await refreshFileTree();
  }

  async function browseWorkspace(path = workspaceDraft || workspaceRoot) {
    const query = new URLSearchParams({ path: String(path || "") });
    const result = await fetch(`/workspace/directories?${query}`).then((res) => res.json());
    setDirectoryBrowser(result);
  }

  async function loadWorkspaceWorkflow(item) {
    if (!item || item.type !== "file") return;
    try {
      let workflow;
      if (item.name.toLowerCase().endsWith(".json")) {
        const query = new URLSearchParams({ path: item.path });
        const result = await fetch(`/workspace/file?${query}`).then((res) => res.json());
        workflow = JSON.parse(result.content);
      } else {
        workflow = (await fetch("/workspace/workflow/extract", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: item.path, filename: item.name }),
        }).then((res) => res.json())).workflow;
      }
      loadWorkflow(workflow, item.name.replace(/\.json$/i, ""));
      setValidation({ valid: true, errors: [], warnings: [] });
    } catch (error) {
      setValidation({ valid: false, errors: [{ level: "error", code: "workspace_file", message: `Could not load ${item.name}: ${error.message}` }], warnings: [] });
    }
  }

  function copyWorkspaceItem(item) {
    setFileClipboard({ operation: "copy", item });
  }

  function cutWorkspaceItem(item) {
    setFileClipboard({ operation: "move", item });
  }

  async function pasteWorkspaceItem(targetDirectory) {
    if (!fileClipboard?.item) return;
    const response = await fetch("/workspace/file-operation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_path: fileClipboard.item.path,
        target_dir: targetDirectory?.type === "directory" ? targetDirectory.path : ".",
        operation: fileClipboard.operation,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setValidation({ valid: false, errors: [{ level: "error", code: "workspace_file_operation", message: result.detail || "Workspace file operation failed." }], warnings: [] });
      return;
    }
    if (fileClipboard.operation === "move") setFileClipboard(null);
    await refreshFileTree();
  }

  async function deleteWorkspaceItem(item) {
    if (!item) return;
    if (confirmFileDelete && !window.confirm(`Move "${item.name}" to .bionodulo_trash?`)) return;
    const response = await fetch("/workspace/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: item.path, trash: true }),
    });
    const result = await response.json();
    if (!response.ok) {
      setValidation({ valid: false, errors: [{ level: "error", code: "workspace_delete", message: result.detail || "Could not delete workspace item." }], warnings: [] });
      return;
    }
    await refreshFileTree();
  }

  function loadTemplate(template) {
    loadWorkflow({ ...template.workflow, environment: template.workflow.environment || environmentSpec }, template.name);
    setRailPanel(null);
  }

  function updateEnvironment(patch) {
    setEnvironmentSpec((current) => normalizeEnvironment({ ...current, ...patch }));
    setManagerDiagnostics(null);
  }

  function addNodeFromRail(meta) {
    const center = reactFlow?.screenToFlowPosition
      ? reactFlow.screenToFlowPosition({ x: Math.round(window.innerWidth / 2), y: Math.round(window.innerHeight / 2) })
      : null;
    addNode(meta, center);
  }

  function openRailItem(item) {
    setPaletteMenu(null);
    setNodeMenu(null);
    setEdgeMenu(null);
    if (item.id === "settings") {
      setSettingsOpen(true);
      setRailPanel(null);
      return;
    }
    if (item.id === "data" && !fileTree) {
      refreshFileTree();
    }
    if (item.id === "console") {
      setRunPanelOpen(false);
      setRailPanel(null);
      setConsoleOpen(true);
      return;
    }
    if (item.id === "envs" && !managerStatus) {
      refreshManagerStatus();
    }
    if (item.id === "envs") {
      setEnvPanelInitialTab("envs");
    }
    setRailPanel((current) => current?.id === item.id ? null : item);
  }

  function openSetupManager() {
    const envItem = LEFT_RAIL_ITEMS.find((item) => item.id === "envs");
    setEnvPanelInitialTab("manager");
    setRailPanel(envItem);
    setRunPanelOpen(false);
    refreshManagerStatus();
  }

  const shellStyle = {
    gridTemplateRows: "42px 38px minmax(0, 1fr)",
  };
  const workspaceStyle = {
    gridTemplateColumns: `58px minmax(0, 1fr) ${runPanelOpen ? "7px" : "0px"} ${runPanelOpen ? `${runPanelWidth}px` : "0px"}`,
  };
  const activeCount = runs.filter((run) => ["queued", "running", "interrupting"].includes(run.status)).length;

  return h(
    "div",
    {
      className: "app-shell canvas-first",
      "data-theme": themePreference,
      style: shellStyle,
      onClick: () => {
        setPaletteMenu(null);
        setNodeMenu(null);
        setGroupMenu(null);
        setEdgeMenu(null);
        setRailPanel((current) => current && ["data", "nodes"].includes(current.id) ? current : null);
      },
      onDragOver: handleDragOver,
      onDragLeave: () => setDropActive(false),
      onDrop: handleDrop,
    },
    h("header", { className: "topbar" },
      h("div", { className: "brand" }, h("span", { className: "mark" }, "BN"), h("div", null, h("strong", null, "BioNodulo"), h("span", null, "Visual bioinformatics pipelines, node by node."))),
      h("div", { className: "top-spacer" }),
        h("div", { className: "run-cluster" },
        h("span", { className: validation.valid ? "validation ok" : "validation bad", title: "Validation status" }, validation.valid ? "Valid" : `${validation.errors.length} issue(s)`),
        h("button", { className: "primary run-button", onClick: () => runWorkflow(false), title: "Queue workflow run" }, "Run"),
        h("button", { onClick: () => exportActiveWorkflow("snakemake"), title: "Export workflow" }, "Export"),
        h("button", { className: "stop-button", onClick: stopRun, title: "Stop active run" }, "x"),
        h("span", { className: activeCount ? "active-count live" : "active-count" }, `${activeCount} active`),
        h("button", { className: runPanelOpen ? "pressed icon-button" : "icon-button", title: "Open runs panel", onClick: (event) => { event.stopPropagation(); setRunPanelOpen((value) => !value); } }, h(Icon, { name: "templates" })),
      ),
    ),
    h("nav", { className: "workflow-tabs", onClick: (event) => event.stopPropagation() },
      workflowTabs.map((tab) => h("button", { key: tab.id, className: tab.id === activeTabId ? "tab active" : "tab", onClick: () => switchWorkflowTab(tab.id) }, h("span", null, tab.name), h("b", { onClick: (event) => closeWorkflowTab(tab.id, event), title: "Close workflow" }, "x"))),
      h("button", { className: "tab add-tab", title: "Add workflow", onClick: addWorkflowTab }, "+"),
    ),
    h("main", { className: "workspace canvas-only", style: workspaceStyle },
      h(LeftRail, {
        items: LEFT_RAIL_ITEMS,
        activeId: settingsOpen ? "settings" : railPanel?.id,
        onSelect: openRailItem,
      }),
      h("section", { className: "canvas" },
        managerDiagnostics?.setup_required ? h(WorkflowSetupBanner, {
          diagnostics: managerDiagnostics,
          environmentSpec,
          mockTools,
          onOpenManager: openSetupManager,
          onDismiss: () => setManagerDiagnostics(null),
        }) : null,
        h(ReactFlow, {
          nodes: displayNodes,
          edges: displayEdges,
          nodeTypes,
          edgeTypes,
          onInit: setReactFlow,
          onNodesChange: handleNodesChange,
          onEdgesChange,
          onConnect,
          onReconnectStart,
          onReconnect,
          onReconnectEnd,
          edgesReconnectable: true,
          defaultEdgeOptions: { type: "bioEdge", reconnectable: true, interactionWidth: 28 },
          onPaneClick: () => { clearSelection(); setCanvasMenu(null); setGroupMenu(null); setNodeMenu(null); setEdgeMenu(null); },
          onPaneContextMenu: openCanvasMenu,
          onPaneDoubleClick: openPalette,
          onNodeClick: handleNodeClick,
          onNodeDoubleClick: (_, node) => { setEditingNodeId(node.id); setNodeMenu(null); setPaletteMenu(null); },
          onNodeContextMenu: openNodeMenu,
          onEdgeContextMenu: openEdgeMenu,
          onMove: (_, viewport) => setZoomPercent(Math.round(viewport.zoom * 100)),
          nodesDraggable: !viewportLocked,
          nodesConnectable: !viewportLocked,
          panOnDrag: !viewportLocked,
          zoomOnScroll: !viewportLocked,
          zoomOnPinch: !viewportLocked,
          snapToGrid,
          snapGrid: [20, 20],
          fitView: true,
        },
          h(Background, null),
          showMiniMap ? h(MiniMap, {
            className: "canvas-minimap",
            style: { width: 220, height: 150, right: 16, bottom: 82 },
            nodeColor: (node) => miniMapNodeColor(node, selectedNodeId),
            nodeStrokeColor: (node) => miniMapNodeStrokeColor(node, selectedNodeId),
            nodeBorderRadius: 4,
            maskColor: "rgba(20, 29, 34, 0.12)",
            pannable: true,
            zoomable: true,
          }) : null,
        ),
        h(CanvasControlIsland, {
          reactFlow,
          showMiniMap,
          setShowMiniMap,
          linksHidden,
          setLinksHidden,
          viewportLocked,
          setViewportLocked,
          zoomPercent,
          onAI: () => setAiOpen(true),
        }),
        selectedNodes.length ? h(SelectionToolbox, {
          selectedNodes,
          reactFlow,
          onDelete: deleteSelectedNodes,
          onBypass: () => updateSelectedNodesUi({ bypassed: true, muted: false }),
          onMute: () => updateSelectedNodesUi({ muted: true, bypassed: false }),
          onUnmute: () => updateSelectedNodesUi({ muted: false, bypassed: false }),
          onPin: () => updateSelectedNodesUi({ pinned: true }),
          onUnpin: () => updateSelectedNodesUi({ pinned: false }),
          onGroup: groupSelectedNodes,
          onCopy: copySelectedNodes,
          onMoreOptions: (event) => {
            event.stopPropagation();
            const rect = event.currentTarget.getBoundingClientRect();
            setNodeMenu({ x: rect.left, y: rect.bottom + 4, nodeId: selectedNodes[0]?.id });
          },
          onSetColor: (nodeId, color) => nodeId && setNodeColor(nodeId, color),
        }) : null,
        groupMenu ? h(GroupContextMenu, {
          menu: groupMenu,
          group: groups.find((g) => g.id === groupMenu.groupId),
          onRename: (name) => renameGroup(groupMenu.groupId, name),
          onSetColor: (color) => setGroupColor(groupMenu.groupId, color),
          onToggleCollapsed: toggleGroupCollapsed,
          onDelete: () => { deleteGroup(groupMenu.groupId); setGroupMenu(null); },
          onClose: () => setGroupMenu(null),
        }) : null,
        canvasMenu ? h(CanvasContextMenu, {
          menu: canvasMenu,
          groupedNodes,
          hasClipboard: Boolean(nodeClipboardRef.current?.nodes?.length),
          onToggleAdd: openAddNodeFromCanvasMenu,
          onAddNode: addNodeFromCanvasMenu,
          onPaste: () => pasteAt(canvasMenu.flowPosition),
          onAddGroup: () => createGroupAt(canvasMenu.flowPosition),
          onClose: () => setCanvasMenu(null),
        }) : null,
        paletteMenu ? h(NodePalette, {
          menu: paletteMenu,
          search: paletteSearch,
          setSearch: setPaletteSearch,
          searchRef: paletteSearchRef,
          nodes: paletteNodes,
          commonNodes,
          onAdd: addNode,
          groupedNodes: paletteGroups,
          onClose: () => setPaletteMenu(null),
        }) : null,
        nodeMenu ? h(NodeContextMenu, {
          menu: nodeMenu,
          node: nodes.find((node) => node.id === nodeMenu.nodeId),
          onEdit: () => { setEditingNodeId(nodeMenu.nodeId); setNodeMenu(null); },
          onDuplicate: () => duplicateNode(nodeMenu.nodeId),
          onDelete: () => deleteNode(nodeMenu.nodeId),
          onToggleOutput: () => toggleWorkflowOutput(nodeMenu.nodeId),
          onTogglePinned: () => updateNodeUi(nodeMenu.nodeId, { pinned: !nodes.find((node) => node.id === nodeMenu.nodeId)?.data?.ui?.pinned }),
          onToggleMuted: () => updateNodeUi(nodeMenu.nodeId, { muted: !nodes.find((node) => node.id === nodeMenu.nodeId)?.data?.ui?.muted }),
          onToggleBypassed: () => updateNodeUi(nodeMenu.nodeId, { bypassed: !nodes.find((node) => node.id === nodeMenu.nodeId)?.data?.ui?.bypassed }),
          onGroupSelected: groupSelectedNodes,
          onForceRun: () => runWorkflow(false, [nodeMenu.nodeId]),
          onValidate: validate,
          onSetColor: (color) => setNodeColor(nodeMenu.nodeId, color),
          onClose: () => setNodeMenu(null),
        }) : null,
        edgeMenu ? h(EdgeContextMenu, {
          menu: edgeMenu,
          edge: edges.find((edge) => edge.id === edgeMenu.edgeId),
          onDelete: () => deleteEdge(edgeMenu.edgeId),
          onClose: () => setEdgeMenu(null),
        }) : null,
        editingNode ? h(NodeEditorModal, {
          node: editingNode,
          validation,
          onParam: updateNodeParams,
          onClose: () => setEditingNodeId(null),
          onToggleOutput: () => toggleWorkflowOutput(editingNode.id),
        }) : null,
        railPanel ? h(RailPanel, {
          item: railPanel,
          nodes,
          edges,
          workflowTabs,
          runs,
          logs,
          registryCount: Object.keys(objectInfo).length,
          environmentSpec,
          updateEnvironment,
          managerStatus,
          managerDiagnostics,
          managerLoading,
          onRefreshManager: refreshManagerStatus,
          onRequestInstall: (plans) => setInstallRequest({ plans }),
          envPanelInitialTab,
          groupedNodes,
          fileTree,
          fileLoading,
          workspaceRoot,
          workspaceDraft,
          setWorkspaceDraft,
          onApplyWorkspaceRoot: applyWorkspaceRoot,
          onLoadWorkspaceWorkflow: loadWorkspaceWorkflow,
          fileClipboard,
          onCopyWorkspaceItem: copyWorkspaceItem,
          onCutWorkspaceItem: cutWorkspaceItem,
          onPasteWorkspaceItem: pasteWorkspaceItem,
          onDeleteWorkspaceItem: deleteWorkspaceItem,
          fileExplorerDepth,
          setFileExplorerDepth,
          showHiddenFiles,
          setShowHiddenFiles,
          templates: WORKFLOW_TEMPLATES,
          onAddNode: addNodeFromRail,
          onRefreshFiles: refreshFileTree,
          onLoadTemplate: loadTemplate,
          onClose: () => setRailPanel(null),
        }) : null,
        consoleOpen ? h(ConsoleDock, {
          logs,
          runs,
          queue,
          height: consoleHeight,
          setHeight: setConsoleHeight,
          onClose: () => setConsoleOpen(false),
          onClear: () => setLogs([]),
        }) : null,
      ),
      runPanelOpen ? h("div", { className: "resize-handle vertical", title: "Drag to resize runs panel", onPointerDown: startRunPanelResize }) : null,
      runPanelOpen ? h("aside", { className: "run-drawer", onClick: (event) => event.stopPropagation() },
        h("div", { className: "panel-title" }, h("strong", null, "Runs"), h("button", { title: "Close run panel", onClick: () => setRunPanelOpen(false) }, "x")),
        h("div", { className: "env-tabs" }, ["queue", "history", "logs", "previews"].map((tab) => h("button", { key: tab, className: runPanelTab === tab ? "active" : "", onClick: () => setRunPanelTab(tab) }, tab))),
        runPanelTab === "queue" ? h("div", { className: "drawer-section" },
          h("p", null, `Current: ${queue.current || "none"} / Pending: ${(queue.pending || []).length}`),
          h("div", { className: "manager-actions" }, h("button", { onClick: refreshQueue }, "Refresh"), h("button", { onClick: clearQueue }, "Clear pending"), h("button", { onClick: stopRun }, "Interrupt current")),
          h("div", { className: "runs" }, runs.filter((run) => ["queued", "running", "interrupting"].includes(run.status)).map((run) => h("button", { key: run.run_id, onClick: () => setCurrentRunId(run.run_id) }, `${run.run_id} / ${run.status}`))),
          h("div", { className: "drawer-section" }, h("h3", null, "Validation"), [...(validation.errors || []), ...(validation.warnings || [])].slice(0, 8).map((issue, idx) => h("p", { key: idx, className: issue.level === "warning" ? "warn" : "err" }, `${issue.node_id || "workflow"}: ${issue.message}`))),
        ) : null,
        runPanelTab === "history" ? h("div", { className: "drawer-section" },
          h("div", { className: "runs" }, runs.slice(0, queueHistorySize).map((run) => h("div", { key: run.run_id, className: "asset-row" },
            h("strong", null, `${run.run_id} / ${run.status}`),
            h("span", null, run.workflow_name),
            h("small", null, run.error || `${Object.keys(run.node_statuses || {}).length} node(s)`),
            h("button", { onClick: () => runWorkflow(false, []) }, "Rerun active workflow"),
            h("button", { onClick: () => loadRunSnapshot(run.run_id) }, "Load snapshot"),
          ))),
        ) : null,
        runPanelTab === "logs" ? h("div", { className: "drawer-section logs" }, logs.slice(-120).map((line, idx) => h("pre", { key: idx }, `[${line.node_id}] ${line.stream}: ${line.line}`))) : null,
        runPanelTab === "previews" ? h("div", { className: "drawer-section" },
          runs.slice(0, 10).flatMap((run) => Object.entries(run.previews || {}).flatMap(([nodeId, previews]) => previews.map((preview, index) => h("div", { key: `${run.run_id}-${nodeId}-${index}`, className: "asset-row" },
            h("strong", null, preview.label || nodeId),
            h("span", null, run.run_id),
            h("code", null, preview.path),
          )))),
        ) : null,
      ) : null,
    ),
    settingsOpen ? h(SettingsModal, {
      mockTools,
      setMockTools,
      runPanelOpen,
      setRunPanelOpen,
      runPanelWidth,
      setRunPanelWidth,
      nodeCount: nodes.length,
      edgeCount: edges.length,
      workflowCount: workflowTabs.length,
      registryCount: Object.keys(objectInfo).length,
      showMiniMap,
      setShowMiniMap,
      linksHidden,
      setLinksHidden,
      viewportLocked,
      setViewportLocked,
      consoleOpen,
      setConsoleOpen,
      consoleHeight,
      setConsoleHeight,
      autoSaveMode,
      setAutoSaveMode,
      preserveView,
      setPreserveView,
      queueHistorySize,
      setQueueHistorySize,
      fileExplorerDepth,
      setFileExplorerDepth,
      showHiddenFiles,
      setShowHiddenFiles,
      strongHashing,
      setStrongHashing,
      tooltipsEnabled,
      setTooltipsEnabled,
      snapToGrid,
      setSnapToGrid,
      themePreference,
      setThemePreference,
      confirmFileDelete,
      setConfirmFileDelete,
      llmSettings,
      updateLlmSettings,
      onClose: () => setSettingsOpen(false),
    }) : null,
    dropActive ? h("div", { className: "drop-overlay" }, h("div", null, h("strong", null, "Drop workflow or output"), h("span", null, "Load workflow JSON or embedded BioNodulo metadata"))) : null,
    aiOpen ? h(AIWorkflowModal, {
      messages: aiMessages,
      busy: aiBusy,
      settings: llmSettings,
      onSend: sendAIMessage,
      onApplyWorkflow: (workflow) => {
        if (!workflow) return;
        try {
          loadWorkflow(workflow, "AI edited workflow");
          setAiOpen(false);
        } catch (error) {
          console.error("Failed to apply AI workflow", error);
        }
      },
      onClose: () => setAiOpen(false),
    }) : null,
    installRequest ? h(InstallConfirmModal, {
      plans: installRequest.plans || [],
      result: installResult,
      onConfirm: async () => { await installPlans(installRequest.plans || []); },
      onClose: () => { setInstallRequest(null); setInstallResult(null); },
    }) : null,
    exportResult ? h(ExportModal, {
      result: exportResult,
      onExport: exportActiveWorkflow,
      onClose: () => setExportResult(null),
    }) : null,
  );
}

function NodePalette({ menu, search, setSearch, searchRef, nodes, commonNodes, groupedNodes, onAdd, onClose }) {
  const style = {
    left: clamp(menu.x, 12, window.innerWidth - 390),
    top: clamp(menu.y, 70, window.innerHeight - 470),
  };
  return h(
    "div",
    { className: "canvas-menu", style, onClick: (event) => event.stopPropagation(), onContextMenu: (event) => event.preventDefault() },
    h("div", { className: "context-head" }, h("strong", null, "Add Node"), h("button", { onClick: onClose, title: "Close menu" }, "x")),
    h("input", { ref: searchRef, className: "search", placeholder: "Search FastQC, trim, bam, quality...", value: search, onChange: (event) => setSearch(event.target.value), onKeyDown: (event) => { if (event.key === "Enter" && nodes[0]) onAdd(nodes[0], menu.flowPosition); } }),
    !search ? h("div", { className: "context-section" },
      h("span", null, "Common"),
      commonNodes.map((meta) => h("button", { key: meta.id, className: "context-node", onClick: () => onAdd(meta, menu.flowPosition) }, h("strong", null, meta.display_name), h("small", null, meta.category))),
    ) : null,
    h("div", { className: "palette-category-list" },
      nodes.length === 0 ? h("p", { className: "muted" }, "No matching nodes.") : null,
      Object.entries(groupedNodes).map(([category, metas]) => h("details", { key: category, open: search || ["Input", "Quality Control", "Read preprocessing"].includes(category) },
        h("summary", null, `${category} (${metas.length})`),
        h("div", { className: "context-section" },
          metas.map((meta) => h("button", { key: meta.id, className: "context-node", onClick: () => onAdd(meta, menu.flowPosition) }, h("strong", null, meta.display_name), h("small", null, meta.description || meta.id))),
        ),
      )),
    ),
  );
}

function CanvasControlIsland({ reactFlow, showMiniMap, setShowMiniMap, linksHidden, setLinksHidden, viewportLocked, setViewportLocked, zoomPercent, onAI }) {
  return h("div", { className: "canvas-control-island", onClick: (event) => event.stopPropagation() },
    h("button", { title: "Zoom out", onClick: () => reactFlow?.zoomOut?.({ duration: 160 }) }, "-"),
    h("span", { className: "zoom-readout" }, `${zoomPercent}%`),
    h("button", { title: "Zoom in", onClick: () => reactFlow?.zoomIn?.({ duration: 160 }) }, "+"),
    h("button", { title: "Fit view", onClick: () => reactFlow?.fitView?.({ padding: 0.18, duration: 250 }) }, h(Icon, { name: "fit" })),
    h("button", { className: viewportLocked ? "pressed" : "", title: viewportLocked ? "Unlock canvas" : "Lock canvas", onClick: () => setViewportLocked((value) => !value) }, h(Icon, { name: viewportLocked ? "lock" : "unlock" })),
    h("button", { className: linksHidden ? "pressed" : "", title: "Hide links", onClick: () => setLinksHidden((value) => !value) }, linksHidden ? "Links off" : "Links"),
    h("button", { className: showMiniMap ? "pressed" : "", title: "Show minimap", onClick: () => setShowMiniMap((value) => !value) }, "Map"),
    h("button", { className: "ai-button", title: "Ask AI to help build this workflow", onClick: onAI }, "AI"),
  );
}

function AIWorkflowModal({ messages, busy, settings, onSend, onApplyWorkflow, onClose }) {
  const [draft, setDraft] = useState("");
  const messagesRef = useRef(null);
  useEffect(() => {
    const element = messagesRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages, busy]);
  function submit(event) {
    event.preventDefault();
    onSend(draft);
    setDraft("");
  }
  function onComposerKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!busy && draft.trim()) {
        onSend(draft);
        setDraft("");
      }
    }
  }
  return h(
    "div",
    { className: "modal-backdrop", onClick: onClose },
    h("div", { className: "ai-modal", onClick: (event) => event.stopPropagation() },
      h("div", { className: "editor-head" },
        h("div", null, h("strong", null, "Workflow AI"), h("span", null, `Provider: ${providerLabel(settings.provider)} / ${settings.model || "model not set"}`)),
        h("button", { onClick: onClose, title: "Close AI panel" }, "x"),
      ),
      h("p", { className: "muted" }, settings.api_key ? "The assistant receives project docs, node metadata, and the active workflow JSON when you send a message." : "Add an API key in Settings to use an external LLM. Without one, this panel stays in local guidance mode."),
      h("div", { className: "ai-chat-layout" },
        h("section", { className: "ai-chat" },
          h("div", { className: "ai-messages", ref: messagesRef },
            messages.map((message, index) => h("div", { key: message.id || index, className: `ai-message ${message.role}` },
              h("strong", null, message.role === "user" ? "You" : "BioNodulo AI"),
              h("p", null, message.content || (message.streaming ? "..." : "")),
              message.workflow ? h(WorkflowMiniMap, { currentWorkflow: message.baselineWorkflow, proposedWorkflow: message.workflow, onApplyWorkflow }) : null,
              message.nodeBlueprint ? h("div", { className: "node-blueprint inline" },
                h("strong", null, "Node blueprint"),
                h("pre", null, JSON.stringify(message.nodeBlueprint, null, 2)),
              ) : null,
            )),
            busy ? h("div", { className: "ai-message assistant" }, h("strong", null, "BioNodulo AI"), h("p", null, "Thinking with workflow context...")) : null,
          ),
          h("div", { className: "ai-suggestions" },
            ["Explain this workflow", "Add post-trim QC and MultiQC", "Create an RNA-seq QC template", "Suggest a custom node"].map((text) => h("button", { key: text, onClick: () => setDraft(text) }, text)),
          ),
          h("form", { className: "ai-compose", onSubmit: submit },
            h("textarea", { value: draft, onChange: (event) => setDraft(event.target.value), onKeyDown: onComposerKeyDown, placeholder: "Ask for a workflow edit, a new template, debugging help, or a node blueprint...", disabled: busy, rows: 1 }),
          ),
        ),
      ),
    ),
  );
}

function WorkflowMiniMap({ currentWorkflow, proposedWorkflow, onApplyWorkflow }) {
  const preview = useMemo(() => workflowPreviewModel(currentWorkflow, proposedWorkflow), [currentWorkflow, proposedWorkflow]);
  const applyWorkflow = (event) => {
    event.preventDefault();
    event.stopPropagation();
    onApplyWorkflow(proposedWorkflow);
  };
  if (!preview.nodes.length) {
    return h("div", { className: "workflow-preview empty" },
      h("p", { className: "muted" }, "The proposed workflow is empty."),
      h("button", { type: "button", className: "primary", onClick: applyWorkflow }, "Apply workflow"),
    );
  }
  return h("div", { className: "workflow-preview" },
    h("div", { className: "workflow-preview-flow" }, h(WorkflowOverviewMap, { preview })),
    h("div", { className: "workflow-preview-legend" },
      h("span", { className: "edited" }, "edited"),
      h("span", { className: "new" }, "new"),
      h("span", { className: "deleted" }, "deleted"),
    ),
    h("button", { type: "button", className: "primary", onClick: applyWorkflow }, "Apply workflow"),
  );
}

function WorkflowOverviewMap({ preview }) {
  const model = useMemo(() => workflowOverviewModel(preview.nodes), [preview.nodes]);
  return h("svg", { className: "workflow-overview-map", viewBox: `0 0 ${model.width} ${model.height}`, role: "img", "aria-label": "AI workflow minimap" },
    h("rect", { className: "workflow-overview-bg", x: 0, y: 0, width: model.width, height: model.height, rx: 8 }),
    model.nodes.map((node) => h("rect", {
      key: node.id,
      className: `workflow-overview-node ${node.status || "same"}`,
      x: node.x,
      y: node.y,
      width: node.width,
      height: node.height,
      rx: 5,
      style: {
        fill: miniMapNodeColor({ id: node.id, data: { status: node.status } }),
        stroke: miniMapNodeStrokeColor({ id: node.id, data: { status: node.status } }),
      },
    })),
  );
}

function InstallConfirmModal({ plans, result, onConfirm, onClose }) {
  return h("div", { className: "modal-backdrop", onClick: onClose },
    h("div", { className: "install-modal", onClick: (event) => event.stopPropagation() },
      h("div", { className: "editor-head" },
        h("div", null, h("strong", null, "Confirm Install"), h("span", null, "BioNodulo will run the generated Manager install command(s).")),
        h("button", { onClick: onClose, title: "Close install confirmation" }, "x"),
      ),
      h("p", { className: "warnline" }, "This can download packages or container images and modify your local environment."),
      h("div", { className: "install-plan-list" }, plans.map((plan) => h("div", { key: `${plan.kind}-${plan.target}`, className: "manager-plan" },
        h("strong", null, plan.target),
        h("span", null, plan.kind),
        h("small", null, plan.command ? plan.command.join(" ") : plan.command_hint || "No executable command available."),
      ))),
      result ? h("div", { className: "install-results" },
        h("h4", null, "Result"),
        (result.results || []).map((item, index) => h("pre", { key: index }, `${item.target}: ${item.status}\n${item.stderr || item.stdout || item.message || ""}`)),
      ) : null,
      h("div", { className: "editor-actions" }, h("button", { onClick: onClose }, "Cancel"), h("button", { className: "primary", onClick: onConfirm }, "Confirm install")),
    ),
  );
}

function SelectionToolbox({ selectedNodes, reactFlow, onDelete, onBypass, onMute, onUnmute, onPin, onUnpin, onGroup, onCopy, onMoreOptions, onSetColor }) {
  const bounds = selectedNodes.reduce((acc, node) => ({
    minX: Math.min(acc.minX, node.position.x),
    minY: Math.min(acc.minY, node.position.y),
    maxX: Math.max(acc.maxX, node.position.x + NODE_WIDTH),
  }), { minX: Infinity, minY: Infinity, maxX: -Infinity });
  const anchor = reactFlow?.flowToScreenPosition
    ? reactFlow.flowToScreenPosition({ x: (bounds.minX + bounds.maxX) / 2, y: bounds.minY })
    : { x: window.innerWidth / 2, y: 112 };
  const style = {
    left: clamp(anchor.x - 220, 72, window.innerWidth - 460),
    top: clamp(anchor.y - 52, 86, window.innerHeight - 90),
  };
  const firstNode = selectedNodes[0];
  const currentColor = firstNode?.data?.ui?.color;
  return h("div", { className: "selection-toolbox", style, onClick: (event) => event.stopPropagation() },
    h("span", { className: "selection-toolbox-count" }, `${selectedNodes.length} selected`),
    h("button", { className: "selection-toolbox-icon", title: "Copy (Ctrl+C)", onClick: onCopy }, h(Icon, { name: "copy" })),
    h("button", { className: "selection-toolbox-icon", title: "Color", onClick: () => onSetColor(firstNode?.id, NODE_COLORS[(selectedNodes.indexOf(firstNode) + 1) % NODE_COLORS.length]) },
      h(Icon, { name: "palette" }),
      currentColor ? h("span", { className: "selection-toolbox-color-dot", style: { background: currentColor } }) : null,
    ),
    h("button", { className: "selection-toolbox-icon", title: "Bypass (Ctrl+B)", onClick: onBypass }, h(Icon, { name: "bypass" })),
    h("button", { className: "selection-toolbox-icon", title: "Pin", onClick: onPin }, h(Icon, { name: "pin" })),
    h("button", { className: "selection-toolbox-icon danger", title: "Delete (Del)", onClick: onDelete }, h(Icon, { name: "trash" })),
    h("button", { className: "selection-toolbox-icon selection-toolbox-more", title: "More Options", onClick: onMoreOptions }, h(Icon, { name: "more-vertical" })),
  );
}

function CanvasContextMenu({ menu, groupedNodes, hasClipboard, onToggleAdd, onAddNode, onPaste, onAddGroup, onClose }) {
  const style = {
    left: clamp(menu.x, 12, window.innerWidth - 260),
    top: clamp(menu.y, 70, window.innerHeight - 400),
  };
  const submenuStyle = {
    left: clamp(menu.x + 246, 12, window.innerWidth - 340),
    top: clamp(menu.y + 6, 70, window.innerHeight - 520),
  };
  return h("div", { className: "canvas-context-menu", style, onClick: (event) => event.stopPropagation(), onContextMenu: (event) => event.preventDefault() },
    h("button", { className: menu.addOpen ? "context-menu-row active" : "context-menu-row", onMouseEnter: () => !menu.addOpen && onToggleAdd(), onClick: onToggleAdd },
      h(Icon, { name: "nodes" }),
      h("span", null, "Add Node"),
      h("b", null, ">"),
    ),
    menu.addOpen ? h("div", { className: "context-submenu", style: submenuStyle },
      Object.entries(groupedNodes).map(([category, metas]) => h("details", { key: category, open: ["Input", "Quality Control", "example"].includes(category) },
        h("summary", null, category),
        metas.map((meta) => h("button", { key: meta.id, className: "context-node", onClick: () => onAddNode(meta) },
          h("strong", null, meta.display_name),
          h("small", null, meta.id),
        )),
      )),
    ) : null,
    h("button", { className: "context-menu-row", disabled: !hasClipboard, onClick: onPaste },
      h(Icon, { name: "paste" }),
      h("span", null, "Paste"),
      h("small", null, "Ctrl+V"),
    ),
    h("button", { className: "context-menu-row", onClick: onAddGroup },
      h(Icon, { name: "group" }),
      h("span", null, "Add Group"),
      h("small", null, "Ctrl+G"),
    ),
  );
}

function ExportModal({ result, onExport, onClose }) {
  return h("div", { className: "modal-backdrop", onClick: onClose },
    h("div", { className: "install-modal", onClick: (event) => event.stopPropagation() },
      h("div", { className: "editor-head" },
        h("div", null, h("strong", null, `Export: ${result.format || "workflow"}`), h("span", null, result.filename || "Generated workflow file")),
        h("button", { onClick: onClose, title: "Close export" }, "x"),
      ),
      h("div", { className: "manager-actions" },
        ["snakemake", "nextflow", "cwl", "wdl"].map((format) => h("button", { key: format, className: result.format === format ? "pressed" : "", onClick: () => onExport(format) }, format)),
      ),
      result.warnings?.length ? h("div", { className: "drawer-section" },
        h("h3", null, "Warnings"),
        result.warnings.map((warning, index) => h("p", { key: index, className: "warn" }, warning)),
      ) : null,
      h("pre", { className: "env-json" }, result.content || result.detail || "No export content returned."),
      h("div", { className: "editor-actions" }, h("button", { className: "primary", onClick: onClose }, "Done")),
    ),
  );
}

function LeftRail({ items, activeId, onSelect }) {
  return h(
    "aside",
    { className: "left-rail", onClick: (event) => event.stopPropagation() },
    h("div", { className: "rail-top" },
      items.slice(0, 4).map((item) => h("button", { key: item.id, className: item.id === activeId ? "rail-item active" : "rail-item", title: item.label, onClick: () => onSelect(item) }, h(Icon, { name: item.icon }), h("small", null, item.label))),
    ),
    h("div", { className: "rail-bottom" },
      items.slice(4).map((item) => h("button", { key: item.id, className: item.id === activeId ? "rail-item active" : "rail-item", title: item.label, onClick: () => onSelect(item) }, h(Icon, { name: item.icon }), h("small", null, item.label))),
    ),
  );
}

function Icon({ name }) {
  return h("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" }, h("path", { d: ICON_PATHS[name] || ICON_PATHS.help }));
}

function WorkflowSetupBanner({ diagnostics, environmentSpec, mockTools, onOpenManager, onDismiss }) {
  const runtimeCount = diagnostics?.runtime_plans?.length || 0;
  const toolCount = diagnostics?.missing_tools?.length || 0;
  const nodeCount = diagnostics?.missing_node_types?.length || 0;
  return h("div", { className: "setup-banner", onClick: (event) => event.stopPropagation() },
    h("div", null,
      h("strong", null, mockTools ? "Real-run setup available" : "Workflow setup needed"),
      h("span", null, diagnostics?.setup_summary || "BioNodulo found workflow dependencies that can be prepared from Envs."),
    ),
    h("div", { className: "setup-banner-counts" },
      runtimeCount ? h("b", null, `${runtimeCount} runtime`) : null,
      toolCount ? h("b", null, `${toolCount} tools`) : null,
      nodeCount ? h("b", null, `${nodeCount} nodes`) : null,
      h("b", null, environmentSpec.type),
    ),
    h("button", { className: "primary", onClick: onOpenManager }, "Open Manager"),
    h("button", { className: "icon-button", onClick: onDismiss, title: "Hide setup banner" }, "x"),
  );
}

function RailPanel({ item, nodes, edges, workflowTabs, runs, logs, registryCount, environmentSpec, updateEnvironment, managerStatus, managerDiagnostics, managerLoading, onRefreshManager, onRequestInstall, envPanelInitialTab, groupedNodes, fileTree, fileLoading, workspaceRoot, workspaceDraft, setWorkspaceDraft, onApplyWorkspaceRoot, onLoadWorkspaceWorkflow, fileClipboard, onCopyWorkspaceItem, onCutWorkspaceItem, onPasteWorkspaceItem, onDeleteWorkspaceItem, fileExplorerDepth, setFileExplorerDepth, showHiddenFiles, setShowHiddenFiles, templates, onAddNode, onRefreshFiles, onLoadTemplate, onClose }) {
  const activeRuns = runs.filter((run) => ["queued", "running", "interrupting"].includes(run.status)).length;
  const docked = ["data", "nodes"].includes(item.id);
  return h(
    "div",
    { className: `rail-panel rail-panel-${item.id} ${docked ? "rail-drawer" : ""}`, onClick: (event) => event.stopPropagation() },
    h("div", { className: "context-head" }, h("strong", null, item.label), h("button", { onClick: onClose, title: "Close" }, "x")),
    h("p", { className: "muted" }, item.description),
    item.id === "data" ? h(DataExplorer, { fileTree, fileLoading, workspaceRoot, workspaceDraft, setWorkspaceDraft, onApplyWorkspaceRoot, onLoadWorkspaceWorkflow, fileClipboard, onCopyWorkspaceItem, onCutWorkspaceItem, onPasteWorkspaceItem, onDeleteWorkspaceItem, fileExplorerDepth, setFileExplorerDepth, showHiddenFiles, setShowHiddenFiles, onRefreshFiles }) : null,
    item.id === "nodes" ? h(NodeLibraryPanel, { groupedNodes, onAddNode }) : null,
    item.id === "templates" ? h(TemplatesPanel, { templates, onLoadTemplate }) : null,
    item.id === "envs" ? h(EnvsManagerPanel, { environmentSpec, updateEnvironment, status: managerStatus, diagnostics: managerDiagnostics, loading: managerLoading, registryCount, initialTab: envPanelInitialTab, onRefresh: onRefreshManager, onRequestInstall }) : null,
    item.id === "help" ? h("ul", null,
      h("li", null, "Right-click or double-click empty canvas to add nodes."),
      h("li", null, "Double-click a node to edit its parameters."),
      h("li", null, "Right-click a node for output, duplicate, rerun, docs, and delete actions."),
      h("li", null, "Right-click a connection or drag it away from an input to disconnect."),
      h("li", null, "Drop a workflow .json file on the canvas to load it."),
    ) : null,
  );
}

function DataExplorer({ fileTree, fileLoading, workspaceRoot, workspaceDraft, setWorkspaceDraft, onApplyWorkspaceRoot, onLoadWorkspaceWorkflow, fileClipboard, onCopyWorkspaceItem, onCutWorkspaceItem, onPasteWorkspaceItem, onDeleteWorkspaceItem, fileExplorerDepth, setFileExplorerDepth, showHiddenFiles, setShowHiddenFiles, onRefreshFiles }) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [fileMenu, setFileMenu] = useState(null);
  const flattened = useMemo(() => flattenFiles(fileTree).filter((item) => {
    if (query && !`${item.name} ${item.path}`.toLowerCase().includes(query.toLowerCase())) return false;
    return kind === "all" || fileKind(item) === kind;
  }), [fileTree, query, kind]);
  function openFileMenu(event, item) {
    event.preventDefault();
    event.stopPropagation();
    setFileMenu({ x: event.clientX, y: event.clientY, item });
  }
  function closeFileMenu() {
    setFileMenu(null);
  }
  function copyPath(item) {
    navigator.clipboard?.writeText(item.absolute_path || item.path);
    closeFileMenu();
  }
  async function loadWorkflowItem(item) {
    closeFileMenu();
    await onLoadWorkspaceWorkflow(item);
  }
  async function makeWorkspace(item) {
    closeFileMenu();
    await onApplyWorkspaceRoot(item.absolute_path || item.path);
  }
  function startWorkspaceDrag(event, item) {
    if (!item) return;
    event.dataTransfer.effectAllowed = item.name?.toLowerCase?.().endsWith(".json") ? "copy" : "none";
    event.dataTransfer.setData("application/bionodulo-workspace-file", JSON.stringify(item));
    event.dataTransfer.setData("text/plain", item.absolute_path || item.path);
  }
  return h("div", { className: "file-explorer rail-stack", onClick: closeFileMenu },
    h("div", { className: "explorer-toolbar" },
      h("button", { className: "icon-button", title: "Refresh workspace", onClick: onRefreshFiles }, fileLoading ? "..." : h(Icon, { name: "refresh" })),
      h("input", { className: "search", placeholder: "Search files, runs, FASTQ, BAM, reports...", value: query, onChange: (event) => setQuery(event.target.value) }),
    ),
    h("form", { className: "explorer-workspace-row", onSubmit: (event) => { event.preventDefault(); onApplyWorkspaceRoot(workspaceDraft); } },
      h("span", null, "Workspace"),
      h("input", { value: workspaceDraft || "", placeholder: workspaceRoot || "Type an absolute workspace path...", onChange: (event) => setWorkspaceDraft(event.target.value) }),
      h("button", { type: "submit", title: "Use this workspace" }, "Use"),
    ),
    h("div", { className: "data-chips" },
      ["all", "sequence", "alignment", "variant", "report", "workflow"].map((value) => h("button", { key: value, className: kind === value ? "pressed" : "", onClick: () => setKind(value) }, value)),
    ),
    h("div", { className: "data-options" },
      h("label", null, "Depth", h("input", { type: "number", min: 1, max: 6, value: fileExplorerDepth, onChange: (event) => setFileExplorerDepth(clamp(Number.parseInt(event.target.value || "4", 10), 1, 6)) })),
      h("label", null, h("input", { type: "checkbox", checked: showHiddenFiles, onChange: (event) => setShowHiddenFiles(event.target.checked) }), " Hidden files"),
    ),
    h("div", { className: "explorer-table" },
      h("div", { className: "explorer-head" }, h("span", null, "Name"), h("span", null, "Kind"), h("span", null, "Size")),
      h("div", { className: "explorer-tree" },
        fileTree ? h(FileTree, { item: fileTree, query, kind, root: true, onContextFile: openFileMenu, onOpenFile: loadWorkflowItem, onDragFile: startWorkspaceDrag }) : h("p", { className: "muted" }, "Loading workspace files..."),
      ),
      query || kind !== "all" ? h("div", { className: "explorer-results" },
        h("strong", null, `${flattened.length} matching file(s)`),
        flattened.slice(0, 24).map((item) => h(AssetRow, { key: item.path, item, onContextFile: openFileMenu, onDragFile: startWorkspaceDrag })),
      ) : null,
    ),
    fileMenu ? h(FileContextMenu, { menu: fileMenu, clipboard: fileClipboard, onClose: closeFileMenu, onCopy: (item) => { onCopyWorkspaceItem(item); closeFileMenu(); }, onCut: (item) => { onCutWorkspaceItem(item); closeFileMenu(); }, onPaste: async (item) => { closeFileMenu(); await onPasteWorkspaceItem(item); }, onDelete: async (item) => { closeFileMenu(); await onDeleteWorkspaceItem(item); }, onCopyPath: copyPath, onLoadWorkflow: loadWorkflowItem, onSetWorkspace: makeWorkspace }) : null,
  );
}

function DirectoryBrowser({ browser, draft, setDraft, onBrowse, onChoose, onClose }) {
  return h("div", { className: "directory-picker" },
    h("div", { className: "directory-picker-head" },
      h("strong", null, "Choose workspace"),
      h("button", { title: "Close browser", onClick: onClose }, "x"),
    ),
    h("div", { className: "directory-current" },
      h("input", { value: draft || browser.path, onChange: (event) => setDraft(event.target.value), onKeyDown: (event) => { if (event.key === "Enter") onBrowse(event.currentTarget.value); } }),
      h("button", { onClick: () => onBrowse(draft || browser.path) }, "Go"),
      h("button", { className: "primary", onClick: () => onChoose(draft || browser.path) }, "Use"),
    ),
    h("div", { className: "directory-quick" }, (browser.quick_roots || []).map((item) => h("button", { key: item.path, onClick: () => { setDraft(item.path); onBrowse(item.path); } }, item.name))),
    browser.parent ? h("button", { className: "directory-row parent", onClick: () => { setDraft(browser.parent); onBrowse(browser.parent); } }, "..", h("span", null, browser.parent)) : null,
    h("div", { className: "directory-list" }, (browser.entries || []).map((item) => h("button", { key: item.path, className: "directory-row", onClick: () => { setDraft(item.path); onBrowse(item.path); }, onDoubleClick: () => onChoose(item.path) },
      h(Icon, { name: "folder" }),
      h("span", null, item.name),
      h("code", null, item.path),
    ))),
  );
}

function FileTree({ item, query = "", kind = "all", root = false, onContextFile, onOpenFile, onDragFile }) {
  if (!item) return null;
  const children = (item.children || []).filter((child) => {
    if (child.type === "directory") return true;
    if (query && !`${child.name} ${child.path}`.toLowerCase().includes(query.toLowerCase())) return false;
    return kind === "all" || fileKind(child) === kind;
  });
  if (item.type === "directory") {
    return h("details", { className: "file-item directory", open: root || item.path === "runs" || item.path === "examples", onContextMenu: (event) => onContextFile?.(event, item) },
      h("summary", null,
        h("span", { className: "file-name" }, h(Icon, { name: "folder" }), h("code", null, item.name)),
        h("span", null, "folder"),
        h("small", null, `${children.length} item(s)`),
      ),
      children.length ? h("div", { className: "file-children" }, children.map((child) => h(FileTree, { key: child.path, item: child, query, kind, onContextFile, onOpenFile, onDragFile }))) : h("small", { className: "muted" }, "No matching files"),
    );
  }
  return h("div", { className: `file-item ${item.type}`, draggable: item.name.toLowerCase().endsWith(".json"), onDragStart: (event) => onDragFile?.(event, item), onContextMenu: (event) => onContextFile?.(event, item), onDoubleClick: () => item.name.toLowerCase().endsWith(".json") ? onOpenFile?.(item) : null },
    h("div", null,
      h("span", { className: "file-name" }, h(Icon, { name: "templates" }), h("code", { title: item.path }, item.name)),
      h("span", null, fileKind(item)),
      item.size != null ? h("small", null, formatBytes(item.size)) : h("small", null, ""),
    ),
  );
}

function AssetRow({ item, onContextFile, onDragFile }) {
  return h("div", { className: `asset-row kind-${fileKind(item)}`, draggable: item.name.toLowerCase().endsWith(".json"), onDragStart: (event) => onDragFile?.(event, item), onContextMenu: (event) => onContextFile?.(event, item) },
    h("strong", null, item.name),
    h("span", null, fileKind(item)),
    h("code", null, item.path),
    item.size != null ? h("small", null, formatBytes(item.size)) : null,
  );
}

function FileContextMenu({ menu, clipboard, onClose, onCopy, onCut, onPaste, onDelete, onCopyPath, onLoadWorkflow, onSetWorkspace }) {
  const item = menu.item;
  const isWorkflow = item.type === "file";
  const canPaste = clipboard?.item && item.type === "directory";
  return h("div", { className: "file-menu", style: { left: menu.x, top: menu.y }, onClick: (event) => event.stopPropagation(), onContextMenu: (event) => event.preventDefault() },
    h("div", { className: "context-head" }, h("strong", null, item.name), h("button", { onClick: onClose, title: "Close" }, "x")),
    h("button", { onClick: () => onCut(item) }, "Cut"),
    h("button", { onClick: () => onCopy(item) }, "Copy"),
    h("button", { disabled: !canPaste, onClick: () => onPaste(item) }, clipboard?.item ? `Paste ${clipboard.item.name}` : "Paste"),
    h("button", { className: "danger", onClick: () => onDelete(item) }, "Delete"),
    isWorkflow ? h("button", { onClick: () => onLoadWorkflow(item) }, "Load workflow") : null,
    item.type === "directory" ? h("button", { onClick: () => onSetWorkspace(item) }, "Use as workspace") : null,
    h("button", { onClick: () => onCopyPath(item) }, "Copy path"),
    h("button", { onClick: () => onCopyPath({ ...item, absolute_path: item.path }) }, "Copy relative path"),
    h("small", null, item.absolute_path || item.path),
  );
}

function NodeLibraryPanel({ groupedNodes, onAddNode }) {
  const [query, setQuery] = useState("");
  const filteredGroups = Object.fromEntries(Object.entries(groupedNodes).map(([category, metas]) => [
    category,
    metas.filter((meta) => `${meta.display_name} ${meta.id} ${meta.description || ""} ${(meta.search_aliases || []).join(" ")}`.toLowerCase().includes(query.toLowerCase())),
  ]).filter(([, metas]) => metas.length));
  return h("div", { className: "node-library-panel" },
    h("input", { className: "search", placeholder: "Search nodes, tools, aliases...", value: query, onChange: (event) => setQuery(event.target.value) }),
    Object.entries(filteredGroups).map(([category, metas]) => h("details", { key: category, open: Boolean(query) || ["Input", "Quality Control", "Read preprocessing"].includes(category) },
      h("summary", null, `${category} (${metas.length})`),
      h("div", { className: "node-list" }, metas.map((meta) => h("button", { key: meta.id, className: "node-list-row", onClick: () => onAddNode(meta) },
        h("strong", null, meta.display_name),
        h("span", null, meta.id),
        h("small", null, meta.description || meta.category),
      ))),
    )),
    Object.keys(filteredGroups).length ? null : h("p", { className: "muted" }, "No matching nodes."),
  );
}

function TemplatesPanel({ templates, onLoadTemplate }) {
  return h("div", { className: "rail-cards" },
    templates.map((template) => h("button", { key: template.id, className: "rail-card", onClick: () => onLoadTemplate(template) }, h("strong", null, template.name), h("small", null, template.description))),
  );
}

function EnvsManagerPanel({ environmentSpec, updateEnvironment, status, diagnostics, loading, registryCount, initialTab = "envs", onRefresh, onRequestInstall }) {
  const [tab, setTab] = useState(initialTab || "envs");
  const [detailRuntime, setDetailRuntime] = useState(null);
  const [registry, setRegistry] = useState([]);
  const [gitUrl, setGitUrl] = useState("");
  const [managerResult, setManagerResult] = useState(null);
  useEffect(() => {
    setTab(initialTab || "envs");
  }, [initialTab]);
  useEffect(() => {
    if (tab === "manager") fetch("/manager/registry").then((res) => res.json()).then((data) => setRegistry(data.registry || [])).catch(() => setRegistry([]));
  }, [tab]);
  const tools = status?.tools || [];
  const missingTools = tools.filter((tool) => !tool.available);
  const plans = diagnostics?.install_plans || [];
  const runtimePlans = diagnostics?.runtime_plans || [];
  const recommendedPlans = plans.filter((plan) => plan.recommended || ["environment", "tool", "custom_node"].includes(plan.kind));
  const selectedRuntimePlan = runtimePlans.find((plan) => plan.target?.toLowerCase?.().includes(environmentSpec.type));
  const runtime = status?.runtimes?.[environmentSpec.type];
  const workflowTools = Array.from(new Set([...(diagnostics?.missing_tools || []).map((tool) => tool.name), ...tools.map((tool) => tool.name)])).filter(Boolean).sort();
  const runtimeCards = [
    { type: "conda", label: "Conda", icon: "snake", color: "conda", env: normalizeEnvironment(environmentSpec.type === "conda" ? environmentSpec : envDefaultsFor("conda")) },
    { type: "docker", label: "Docker", icon: "docker", color: "docker", env: normalizeEnvironment(environmentSpec.type === "docker" ? environmentSpec : envDefaultsFor("docker")) },
    { type: "apptainer", label: "Apptainer", icon: "apptainer", color: "apptainer", env: normalizeEnvironment(environmentSpec.type === "apptainer" ? environmentSpec : envDefaultsFor("apptainer")) },
  ];
  const selected = detailRuntime ? runtimeCards.find((item) => item.type === detailRuntime) : null;
  const managerSections = [
    { id: "undefined", title: "Undefined Node Types", rows: (diagnostics?.missing_node_types || []).map((nodeType) => ({ name: nodeType, status: "missing", detail: "No registered BioNodulo node type provides this workflow node.", plan: plans.find((plan) => plan.target === nodeType) })) },
    { id: "tools", title: "External Tools", rows: tools.map((tool) => ({ name: tool.name, status: tool.available ? "available" : "missing", detail: tool.available ? tool.path : tool.install_hint, plan: plans.find((plan) => plan.target === tool.name) })) },
    { id: "missing", title: "Missing From Active Workflow", rows: plans.map((plan) => ({ name: plan.target, status: plan.status || "planned", detail: plan.command ? plan.command.join(" ") : plan.command_hint, plan })) },
    { id: "custom", title: "Custom Node Packages", rows: (status?.custom_packages || []).map((pkg) => ({ name: pkg.name, status: pkg.type, detail: pkg.path })) },
    { id: "snapshots", title: "Snapshots", rows: [{ name: "Environment snapshot", status: "planned", detail: "Record node packs, runtime image/env, package hints, and custom node state before updates." }] },
  ];
  const installablePlans = plans.filter(Boolean);
  function createEnvironment(type = environmentSpec.type || "conda") {
    const defaults = envDefaultsFor(type);
    updateEnvironment({
      ...defaults,
      name: `${type}-workflow-${Date.now().toString().slice(-4)}`,
      packages: type === "conda" ? workflowTools : defaults.packages,
      notes: "Created from the active workflow dependency scan.",
    });
    setDetailRuntime(type);
  }
  async function installGitPackage() {
    const trimmed = gitUrl.trim();
    if (!trimmed) return;
    const result = await fetch("/manager/install-git", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: trimmed }),
    }).then((res) => res.json());
    setManagerResult(result);
    onRefresh();
  }
  async function reloadCustomNodes() {
    const result = await fetch("/manager/reload", { method: "POST" }).then((res) => res.json());
    setManagerResult(result);
    onRefresh();
  }
  return h("div", { className: "env-manager rail-stack" },
    h("div", { className: "env-tabs" },
      h("button", { className: tab === "envs" ? "active" : "", onClick: () => setTab("envs") }, "Envs"),
      h("button", { className: tab === "manager" ? "active" : "", onClick: () => setTab("manager") }, "Manager"),
    ),
    tab === "envs" ? h("div", { className: "envs-tab" },
      h("div", { className: "env-header-actions" },
        h("strong", null, "Available Environments"),
        h("button", { title: "Create environment", className: "icon-button", onClick: () => createEnvironment("conda") }, "+"),
      ),
      h("div", { className: "runtime-groups" }, runtimeCards.map((card) => h("button", {
        key: card.type,
        className: `runtime-card ${card.color} ${environmentSpec.type === card.type ? "selected" : ""}`,
        onClick: () => {
          updateEnvironment(environmentSpec.type === card.type ? environmentSpec : envDefaultsFor(card.type));
          setDetailRuntime(card.type);
        },
      },
        h(Icon, { name: card.icon }),
        h("strong", null, card.label),
        h("span", null, card.env.name),
      ))),
      selected ? h("section", { className: `runtime-detail ${selected.color}` },
        h("div", { className: "runtime-detail-head" },
          h("h4", null, `${selected.label} environment`),
          h("button", { onClick: () => setDetailRuntime(null), title: "Hide details" }, "x"),
        ),
        h("label", { className: "field" }, h("span", null, "Environment name"), h("input", { value: environmentSpec.name || "", onChange: (event) => updateEnvironment({ name: event.target.value }) })),
        environmentSpec.type === "conda" ? h("div", null,
          h("label", { className: "field" }, h("span", null, "Environment YAML"), h("input", { value: environmentSpec.file || "", onChange: (event) => updateEnvironment({ file: event.target.value }) })),
          h("label", { className: "field" }, h("span", null, "Channels"), h("textarea", { value: (environmentSpec.channels || []).join("\n"), onChange: (event) => updateEnvironment({ channels: lines(event.target.value) }) })),
          h("label", { className: "field" }, h("span", null, "Packages"), h("textarea", { value: (environmentSpec.packages || []).join("\n"), onChange: (event) => updateEnvironment({ packages: lines(event.target.value) }) })),
        ) : null,
        environmentSpec.type === "docker" ? h("div", null,
          h("label", { className: "field" }, h("span", null, "Docker image"), h("input", { value: environmentSpec.image || "", onChange: (event) => updateEnvironment({ image: event.target.value }) })),
          h("label", { className: "field" }, h("span", null, "Mounts"), h("textarea", { value: (environmentSpec.mounts || []).join("\n"), onChange: (event) => updateEnvironment({ mounts: lines(event.target.value) }) })),
        ) : null,
        environmentSpec.type === "apptainer" ? h("div", null,
          h("label", { className: "field" }, h("span", null, "SIF file"), h("input", { value: environmentSpec.file || "", onChange: (event) => updateEnvironment({ file: event.target.value }) })),
          h("label", { className: "field" }, h("span", null, "Remote image"), h("input", { value: environmentSpec.image || "", onChange: (event) => updateEnvironment({ image: event.target.value }) })),
          h("label", { className: "field" }, h("span", null, "Mounts"), h("textarea", { value: (environmentSpec.mounts || []).join("\n"), onChange: (event) => updateEnvironment({ mounts: lines(event.target.value) }) })),
        ) : null,
        h("label", { className: "field" }, h("span", null, "Notes"), h("textarea", { value: environmentSpec.notes || "", onChange: (event) => updateEnvironment({ notes: event.target.value }) })),
        h("p", { className: runtime?.available ? "okline" : "warnline" }, runtime ? `${environmentSpec.type} runtime: ${runtime.available ? runtime.path : "not found"}` : "Open Manager to scan runtime availability."),
      ) : h("p", { className: "muted" }, "Click Conda, Docker, or Apptainer to view and edit that environment."),
    ) : h("div", { className: "manager-tab rail-stack" },
      h("section", { className: "setup-card" },
        h("div", { className: "setup-card-head" },
          h("div", null,
            h("h4", null, "Workflow Setup"),
            h("p", { className: "muted" }, diagnostics?.setup_summary || "Scan the active workflow to find missing runtimes, tools, and node packages."),
          ),
          h("span", { className: diagnostics?.setup_required ? "setup-status missing" : "setup-status ok" }, diagnostics?.setup_required ? "setup needed" : "ready"),
        ),
        h("div", { className: "setup-checklist" },
          h("div", null, h("strong", null, "Runtime"), h("span", null, runtime?.available ? `${environmentSpec.type} ready` : `${environmentSpec.type} not ready`)),
          h("div", null, h("strong", null, "Environment"), h("span", null, environmentSpec.name || "unnamed environment")),
          h("div", null, h("strong", null, "Tools"), h("span", null, diagnostics?.missing_tools?.length ? `${diagnostics.missing_tools.length} missing` : "all detected tools ready")),
          h("div", null, h("strong", null, "Nodes"), h("span", null, diagnostics?.missing_node_types?.length ? `${diagnostics.missing_node_types.length} missing` : "all node types registered")),
        ),
        h("div", { className: "setup-actions" },
          h("button", { onClick: onRefresh }, loading ? "Scanning..." : "Scan active workflow"),
          h("button", { disabled: !workflowTools.length, onClick: () => createEnvironment(environmentSpec.type || "conda") }, "New env for workflow"),
          h("button", { className: "primary", disabled: !recommendedPlans.length, onClick: () => onRequestInstall(recommendedPlans.length ? recommendedPlans : installablePlans) }, "Auto install recommended"),
        ),
        runtimePlans.length ? h("div", { className: "runtime-plan-list" }, runtimePlans.map((plan) => h("div", { key: `${plan.action}-${plan.target}`, className: plan.recommended ? "runtime-plan-card recommended" : "runtime-plan-card" },
          h("strong", null, plan.target),
          h("span", null, plan.recommended ? "recommended" : "optional"),
          h("small", null, plan.command?.length ? plan.command.join(" ") : plan.command_hint),
          h("button", { onClick: () => onRequestInstall([plan]) }, plan.command?.length || plan.action === "install_managed_micromamba" ? "Install" : "Show instructions"),
        ))) : null,
        selectedRuntimePlan ? h("p", { className: "muted" }, `${selectedRuntimePlan.target} can be installed from this Manager after confirmation.`) : null,
      ),
      h("div", { className: "manager-actions" },
        h("button", { disabled: !workflowTools.length, onClick: () => createEnvironment("conda") }, "New Conda env"),
        h("button", { disabled: !workflowTools.length, onClick: () => createEnvironment("docker") }, "Use Docker"),
        h("button", { disabled: !workflowTools.length, onClick: () => createEnvironment("apptainer") }, "Use Apptainer"),
        h("button", { onClick: reloadCustomNodes }, "Reload nodes"),
        h("button", { className: "primary", disabled: !installablePlans.length, onClick: () => onRequestInstall(installablePlans) }, "Install all to selected env"),
      ),
      h("section", null,
        h("h4", null, "Custom Node Registry"),
        h("label", { className: "field" }, h("span", null, "Git URL"), h("input", { value: gitUrl, onChange: (event) => setGitUrl(event.target.value), placeholder: "https://github.com/org/bionodulo-nodes.git" })),
        h("div", { className: "manager-actions" }, h("button", { className: "primary", disabled: !gitUrl.trim(), onClick: installGitPackage }, "Install Git package")),
        managerResult ? h("pre", { className: "env-json" }, JSON.stringify(managerResult, null, 2)) : null,
        registry.length ? h("div", { className: "rail-cards" }, registry.map((entry) => h("div", { key: entry.id || entry.url, className: "tool-row" },
          h("strong", null, entry.name || entry.id),
          h("span", null, entry.status || "registry"),
          h("small", null, entry.description || entry.url),
        ))) : h("p", { className: "muted" }, "No registry entries configured."),
      ),
      h("p", { className: "muted" }, status ? `Selected ${environmentSpec.type}: ${environmentSpec.name}. Python ${status.python} / ${status.registered_nodes} registered node type(s)` : `${registryCount} registered node type(s)`),
      managerSections.map((section) => h("section", { key: section.id },
        h("h4", null, section.title),
        section.rows.length ? section.rows.map((row) => h("div", { key: `${section.id}-${row.name}`, className: row.status === "available" ? "tool-row ok" : "tool-row missing" },
          h("strong", null, row.name),
          h("span", null, row.status),
          h("small", null, row.detail),
          row.plan ? h("button", { onClick: () => onRequestInstall([row.plan]) }, "Install") : null,
        )) : h("p", { className: "muted" }, "None."),
      )),
    ),
  );
}

function ConsoleDock({ logs, runs, queue, height, setHeight, onClose, onClear }) {
  const activeRuns = runs.filter((run) => ["queued", "running", "interrupting"].includes(run.status)).length;
  function startResize(event) {
    event.preventDefault();
    const move = (moveEvent) => setHeight(clamp(window.innerHeight - moveEvent.clientY - 10, 140, 440));
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      document.body.classList.remove("is-resizing-y");
    };
    document.body.classList.add("is-resizing-y");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }
  return h("div", { className: "console-dock", style: { height } },
    h("div", { className: "console-resize", onPointerDown: startResize, title: "Drag to resize console" }),
    h("div", { className: "console-title" },
      h("strong", null, "BioNodulo Console"),
      h("span", null, `current=${queue.current || "none"} pending=${(queue.pending || []).length} active=${activeRuns}`),
      h("button", { onClick: onClear }, "Clear"),
      h("button", { onClick: onClose, title: "Close console" }, "x"),
    ),
    h("div", { className: "console-terminal" },
      logs.length
        ? logs.slice(-250).map((line, idx) => h("pre", { key: idx }, `> [${line.node_id}] ${line.stream}: ${line.line}`))
        : h("pre", null, "> waiting for workflow logs..."),
    ),
  );
}

function SettingsModal({
  mockTools,
  setMockTools,
  runPanelOpen,
  setRunPanelOpen,
  runPanelWidth,
  setRunPanelWidth,
  nodeCount,
  edgeCount,
  workflowCount,
  registryCount,
  showMiniMap,
  setShowMiniMap,
  linksHidden,
  setLinksHidden,
  viewportLocked,
  setViewportLocked,
  consoleOpen,
  setConsoleOpen,
  consoleHeight,
  setConsoleHeight,
  autoSaveMode,
  setAutoSaveMode,
  preserveView,
  setPreserveView,
  queueHistorySize,
  setQueueHistorySize,
  fileExplorerDepth,
  setFileExplorerDepth,
  showHiddenFiles,
  setShowHiddenFiles,
  strongHashing,
  setStrongHashing,
  tooltipsEnabled,
  setTooltipsEnabled,
  snapToGrid,
  setSnapToGrid,
  themePreference,
  setThemePreference,
  confirmFileDelete,
  setConfirmFileDelete,
  llmSettings,
  updateLlmSettings,
  onClose,
}) {
  return h(
    "div",
    { className: "modal-backdrop", onClick: onClose },
    h("div", { className: "settings-modal", onClick: (event) => event.stopPropagation() },
      h("div", { className: "editor-head" },
        h("div", null, h("strong", null, "Settings"), h("span", null, "BioNodulo interface, execution, reproducibility, and workspace preferences")),
        h("button", { onClick: onClose, title: "Close settings" }, "x"),
      ),
      h("div", { className: "settings-grid" },
        h("section", null,
          h("h4", null, "Appearance"),
          h("label", { className: "field" }, h("span", null, "Theme"), h("select", { value: themePreference, onChange: (event) => setThemePreference(event.target.value) },
            h("option", { value: "system" }, "System"),
            h("option", { value: "dark" }, "Dark"),
            h("option", { value: "light" }, "Light"),
          )),
          h("label", { className: "setting-row" }, h("span", null, "Show minimap"), h("input", { type: "checkbox", checked: showMiniMap, onChange: (event) => setShowMiniMap(event.target.checked) })),
          h("label", { className: "setting-row" }, h("span", null, "Open console dock"), h("input", { type: "checkbox", checked: consoleOpen, onChange: (event) => setConsoleOpen(event.target.checked) })),
          h("label", { className: "field" }, h("span", null, "Console height"), h("input", { type: "number", min: 140, max: 440, value: consoleHeight, onChange: (event) => setConsoleHeight(clamp(Number.parseInt(event.target.value || "220", 10), 140, 440)) })),
        ),
        h("section", null,
          h("h4", null, "Canvas"),
          h("label", { className: "setting-row" }, h("span", null, "Hide links"), h("input", { type: "checkbox", checked: linksHidden, onChange: (event) => setLinksHidden(event.target.checked) })),
          h("label", { className: "setting-row" }, h("span", null, "Lock canvas"), h("input", { type: "checkbox", checked: viewportLocked, onChange: (event) => setViewportLocked(event.target.checked) })),
          h("label", { className: "setting-row" }, h("span", null, "Snap nodes to grid"), h("input", { type: "checkbox", checked: snapToGrid, onChange: (event) => setSnapToGrid(event.target.checked) })),
          h("label", { className: "setting-row" }, h("span", null, "Parameter tooltips"), h("input", { type: "checkbox", checked: tooltipsEnabled, onChange: (event) => setTooltipsEnabled(event.target.checked) })),
        ),
        h("section", null,
          h("h4", null, "Workflow"),
          h("label", { className: "field" }, h("span", null, "Auto save"), h("select", { value: autoSaveMode, onChange: (event) => setAutoSaveMode(event.target.value) }, h("option", { value: "off" }, "Off"), h("option", { value: "after-delay" }, "After delay"), h("option", { value: "on-run" }, "Before run"))),
          h("label", { className: "setting-row" }, h("span", null, "Restore canvas view"), h("input", { type: "checkbox", checked: preserveView, onChange: (event) => setPreserveView(event.target.checked) })),
          h("label", { className: "field" }, h("span", null, "Queue history size"), h("input", { type: "number", min: 10, max: 1000, value: queueHistorySize, onChange: (event) => setQueueHistorySize(clamp(Number.parseInt(event.target.value || "100", 10), 10, 1000)) })),
        ),
        h("section", null,
          h("h4", null, "Execution"),
          h("label", { className: "setting-row" }, h("span", null, "Mock mode"), h("input", { type: "checkbox", checked: mockTools, onChange: (event) => setMockTools(event.target.checked) })),
          h("label", { className: "setting-row" }, h("span", null, "Stop on first node error"), h("input", { type: "checkbox", checked: true, readOnly: true })),
          h("label", { className: "setting-row" }, h("span", null, "Use strong hashes for small files"), h("input", { type: "checkbox", checked: strongHashing, onChange: (event) => setStrongHashing(event.target.checked) })),
          h("label", { className: "setting-row" }, h("span", null, "Runs drawer open"), h("input", { type: "checkbox", checked: runPanelOpen, onChange: (event) => setRunPanelOpen(event.target.checked) })),
          h("label", { className: "field" }, h("span", null, "Runs drawer width"), h("input", { type: "number", min: 280, max: 560, value: runPanelWidth, onChange: (event) => setRunPanelWidth(clamp(Number.parseInt(event.target.value || "380", 10), 280, 560)) })),
        ),
        h("section", null,
          h("h4", null, "Data Explorer"),
          h("label", { className: "field" }, h("span", null, "Scan depth"), h("input", { type: "number", min: 1, max: 6, value: fileExplorerDepth, onChange: (event) => setFileExplorerDepth(clamp(Number.parseInt(event.target.value || "4", 10), 1, 6)) })),
          h("label", { className: "setting-row" }, h("span", null, "Show hidden files"), h("input", { type: "checkbox", checked: showHiddenFiles, onChange: (event) => setShowHiddenFiles(event.target.checked) })),
          h("label", { className: "setting-row" }, h("span", null, "Confirm delete"), h("input", { type: "checkbox", checked: confirmFileDelete, onChange: (event) => setConfirmFileDelete(event.target.checked) })),
          h("p", { className: "muted" }, "Drag workflow JSON files from Data onto the canvas to import them. Deletes move items to .bionodulo_trash."),
        ),
        h("section", null,
          h("h4", null, "ComfyUI-style UX"),
          h("label", { className: "setting-row" }, h("span", null, "Right-click canvas node search"), h("input", { type: "checkbox", checked: true, readOnly: true })),
          h("label", { className: "setting-row" }, h("span", null, "Double-click nodes to edit"), h("input", { type: "checkbox", checked: true, readOnly: true })),
          h("label", { className: "setting-row" }, h("span", null, "Reconnect by dragging links"), h("input", { type: "checkbox", checked: true, readOnly: true })),
          h("label", { className: "setting-row" }, h("span", null, "Workflow tabs"), h("input", { type: "checkbox", checked: true, readOnly: true })),
        ),
        h("section", null,
          h("h4", null, "AI Assistant"),
          h("label", { className: "field" }, h("span", null, "Provider"), h("select", { value: llmSettings.provider, onChange: (event) => updateLlmSettings(providerDefaults(event.target.value)) },
            h("option", { value: "openai" }, "OpenAI"),
            h("option", { value: "openai-compatible" }, "OpenAI-compatible"),
            h("option", { value: "gemini" }, "Gemini"),
            h("option", { value: "openrouter" }, "OpenRouter"),
          )),
          h("label", { className: "field" }, h("span", null, "Model"), h("input", { value: llmSettings.model, onChange: (event) => updateLlmSettings({ model: event.target.value }) })),
          h("label", { className: "field" }, h("span", null, "Base URL"), h("input", { placeholder: "Optional for compatible providers", value: llmSettings.base_url, onChange: (event) => updateLlmSettings({ base_url: event.target.value }) })),
          h("label", { className: "field" }, h("span", null, "API key"), h("input", { type: "password", placeholder: "Saved in this browser", value: llmSettings.api_key, onChange: (event) => updateLlmSettings({ api_key: event.target.value }) })),
          h("label", { className: "field" }, h("span", null, "Temperature"), h("input", { type: "number", min: 0, max: 1, step: 0.1, value: llmSettings.temperature, onChange: (event) => updateLlmSettings({ temperature: Number.parseFloat(event.target.value || "0.2") }) })),
          h("p", { className: "muted" }, "Chat sends your active workflow and BioNodulo docs to the selected provider when you press Enter in the AI chat."),
        ),
        h("section", null,
          h("h4", null, "Reproducibility"),
          h("ul", null,
            h("li", null, "Every run records workflow JSON, command lines, logs, outputs, and node statuses."),
            h("li", null, "MVP cache keys use paths, file sizes, modified times, params, and upstream cache keys."),
            h("li", null, "Future: lockfiles for tool versions and environment manifests."),
          ),
        ),
        h("section", null,
          h("h4", null, "Current Session"),
          h("ul", null,
            h("li", null, `${workflowCount} workflow tab(s)`),
            h("li", null, `${nodeCount} node(s)`),
            h("li", null, `${edgeCount} connection(s)`),
            h("li", null, `${registryCount} registered node type(s)`),
          ),
        ),
      ),
      h("div", { className: "editor-actions" }, h("button", { className: "primary", onClick: onClose }, "Done")),
    ),
  );
}

function NodeContextMenu({ menu, node, onEdit, onDuplicate, onDelete, onToggleOutput, onTogglePinned, onToggleMuted, onToggleBypassed, onGroupSelected, onForceRun, onValidate, onSetColor, onClose }) {
  if (!node) return null;
  const style = {
    left: clamp(menu.x, 12, window.innerWidth - 300),
    top: clamp(menu.y, 70, window.innerHeight - 560),
  };
  const meta = node.data.meta || {};
  const isPinned = node.data.ui?.pinned;
  const isMuted = node.data.ui?.muted;
  const isBypassed = node.data.ui?.bypassed;
  const isOutput = node.data.workflowOutput;
  const currentColor = node.data.ui?.color;
  const [colorOpen, setColorOpen] = useState(false);

  return h(
    "div",
    { className: "node-menu", style, onClick: (event) => event.stopPropagation(), onContextMenu: (event) => event.preventDefault() },
    h("div", { className: "context-head" },
      h("strong", null, meta.display_name || node.data.type),
      h("button", { onClick: onClose, title: "Close menu" }, "x"),
    ),

    h("div", { className: "node-menu-section" },
      h("button", { className: "node-menu-item", onClick: onEdit },
        h(Icon, { name: "edit" }),
        h("span", null, "Edit"),
      ),
      h("button", { className: "node-menu-item", onClick: onDuplicate },
        h(Icon, { name: "copy" }),
        h("span", null, "Duplicate"),
      ),
      h("button", { className: "node-menu-item", onClick: onToggleOutput },
        h(Icon, { name: "validate" }),
        h("span", null, isOutput ? "Unset Output" : "Set Output"),
      ),
    ),

    h("div", { className: "node-menu-divider" }),

    h("div", { className: "node-menu-section" },
      h("button", { className: "node-menu-item", onClick: () => setColorOpen(!colorOpen) },
        h(Icon, { name: "palette" }),
        h("span", null, "Color"),
        currentColor ? h("span", { className: "node-color-dot", style: { background: currentColor } }) : null,
        h("small", null, ">"),
      ),
      colorOpen ? h("div", { className: "node-color-popup" },
        h("div", { className: "node-color-swatches" },
          NODE_COLORS.map((c) => h("button", {
            key: c.name,
            className: `node-color-swatch-btn ${currentColor === c.title ? "active" : ""}`,
            style: { background: `linear-gradient(135deg, ${c.title} 50%, ${c.body} 50%)` },
            onClick: () => { onSetColor(c); setColorOpen(false); onClose(); },
            title: c.name,
          })),
        ),
        currentColor ? h("button", { className: "node-menu-item node-color-clear", onClick: () => { onSetColor(null); setColorOpen(false); onClose(); } },
          h("span", null, "✕"),
          h("span", null, "No Color"),
        ) : null,
      ) : null,
    ),

    h("div", { className: "node-menu-divider" }),

    h("div", { className: "node-menu-section" },
      h("button", { className: "node-menu-item", onClick: onTogglePinned },
        h(Icon, { name: isPinned ? "pin-off" : "pin" }),
        h("span", null, isPinned ? "Unpin" : "Pin"),
        h("small", null, "P"),
      ),
      h("button", { className: "node-menu-item", onClick: onToggleMuted },
        h(Icon, { name: "mute" }),
        h("span", null, isMuted ? "Unmute" : "Mute"),
        h("small", null, "M"),
      ),
      h("button", { className: "node-menu-item", onClick: onToggleBypassed },
        h(Icon, { name: "bypass" }),
        h("span", null, isBypassed ? "Unbypass" : "Bypass"),
        h("small", null, "B"),
      ),
    ),

    h("div", { className: "node-menu-divider" }),

    h("div", { className: "node-menu-section" },
      h("button", { className: "node-menu-item node-menu-danger", onClick: onDelete },
        h(Icon, { name: "trash" }),
        h("span", null, "Delete"),
        h("small", null, "Del"),
      ),
    ),
  );
}

function EdgeContextMenu({ menu, edge, onDelete, onClose }) {
  if (!edge) return null;
  const style = {
    left: clamp(menu.x, 12, window.innerWidth - 280),
    top: clamp(menu.y, 82, window.innerHeight - 220),
  };
  return h(
    "div",
    { className: "edge-menu", style, onClick: (event) => event.stopPropagation(), onContextMenu: (event) => event.preventDefault() },
    h("div", { className: "context-head" }, h("strong", null, "Connection"), h("button", { onClick: onClose, title: "Close menu" }, "x")),
    h("p", { className: "muted" }, `${edge.source}.${edge.sourceHandle || "output"} -> ${edge.target}.${edge.targetHandle || "input"}`),
    h("button", { onClick: onDelete }, "Disconnect"),
  );
}

function NodeEditorModal({ node, validation, onParam, onClose, onToggleOutput }) {
  const meta = node.data.meta || {};
  const specs = { ...(meta.inputs?.required || {}), ...(meta.inputs?.optional || {}) };
  const nodeIssues = [...(validation.errors || []), ...(validation.warnings || [])].filter((issue) => issue.node_id === node.id);
  return h(
    "div",
    { className: "modal-backdrop", onClick: onClose },
    h("div", { className: "node-editor", onClick: (event) => event.stopPropagation() },
      h("div", { className: "editor-head" },
        h("div", null, h("strong", null, meta.display_name || node.data.type), h("span", null, node.id)),
        h("button", { onClick: onClose, title: "Close editor" }, "x"),
      ),
      h("p", { className: "muted" }, meta.description || ""),
      Object.entries(specs).length ? Object.entries(specs).map(([name, spec]) =>
        h("label", { key: name, className: "field" },
          h("span", null, `${name} (${spec.type})`),
          renderInput(name, node.data.params?.[name], spec, (paramName, value, paramSpec) => onParam(node.id, paramName, value, paramSpec)),
          spec.description ? h("small", null, spec.description) : null,
        ),
      ) : h("p", { className: "muted" }, "This node has no editable parameters."),
      h("div", { className: "editor-section" },
        h("h4", null, "Inputs"),
        h("ul", null, Object.entries(specs).map(([name, spec]) => h("li", { key: name }, `${name}: ${spec.type}`))),
      ),
      h("div", { className: "editor-section" },
        h("h4", null, "Outputs"),
        h("ul", null, (meta.outputs || []).map((output) => h("li", { key: output.name }, `${output.name}: ${output.type}`))),
      ),
      nodeIssues.map((issue, idx) => h("p", { key: idx, className: issue.level === "warning" ? "warn" : "err" }, issue.message)),
      h("div", { className: "editor-actions" },
        h("button", { onClick: onToggleOutput }, node.data.workflowOutput ? "Unset Workflow Output" : "Set Workflow Output"),
        h("button", { className: "primary", onClick: onClose }, "Done"),
      ),
    ),
  );
}

function renderInput(name, value, spec, onParam) {
  if (spec.type === "BOOLEAN") {
    return h("input", { type: "checkbox", checked: Boolean(value), onChange: (event) => onParam(name, event.target.checked, spec) });
  }
  if (spec.type === "INT" || spec.type === "FLOAT") {
    if (spec.widget === "slider") {
      const current = value ?? spec.default ?? spec.min ?? 0;
      return h("div", { className: "range-field" },
        h("input", { type: "range", min: spec.min, max: spec.max, step: spec.step || 1, value: current, onChange: (event) => onParam(name, event.target.value, spec) }),
        h("input", { type: "number", min: spec.min, max: spec.max, step: spec.step || 1, value: current, onChange: (event) => onParam(name, event.target.value, spec) }),
      );
    }
    return h("input", { type: "number", min: spec.min, max: spec.max, value: value ?? "", onChange: (event) => onParam(name, event.target.value, spec) });
  }
  if (Array.isArray(value) || spec.type.endsWith("_LIST")) {
    return h("textarea", { value: Array.isArray(value) ? value.join("\n") : value || "", onChange: (event) => onParam(name, event.target.value, spec) });
  }
  return h("input", { value: value ?? "", onChange: (event) => onParam(name, event.target.value, spec) });
}

function parseParamValue(value, spec) {
  if (spec.type === "INT") return Number.parseInt(value || "0", 10);
  if (spec.type === "FLOAT") return Number.parseFloat(value || "0");
  if (spec.type === "BOOLEAN") return Boolean(value);
  if (spec.type.endsWith("_LIST")) return String(value).split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean);
  return value;
}

function filterNodes(nodes, query) {
  const normalized = query.trim().toLowerCase();
  return nodes
    .filter((meta) => {
      if (!normalized) return true;
      const haystack = [meta.id, meta.display_name, meta.category, meta.description, ...(meta.search_aliases || [])].join(" ").toLowerCase();
      return haystack.includes(normalized);
    })
    .sort((a, b) => `${a.category}${a.display_name}`.localeCompare(`${b.category}${b.display_name}`));
}

function groupNodesByCategory(nodes) {
  return nodes
    .slice()
    .sort((a, b) => `${a.category}${a.display_name}`.localeCompare(`${b.category}${b.display_name}`))
    .reduce((groups, meta) => {
      const category = meta.category || "Other";
      groups[category] = groups[category] || [];
      groups[category].push(meta);
      return groups;
    }, {});
}

function normalizeEnvironment(value) {
  return { ...envDefaultsFor(value?.type || "conda"), ...(value || {}) };
}

function envDefaultsFor(type) {
  if (type === "docker") {
    return { ...DEFAULT_ENVIRONMENT, type: "docker", name: "bionodulo-docker", file: "", image: "quay.io/biocontainers/multiqc:latest", packages: [], channels: [], mounts: [".:/work"] };
  }
  if (type === "apptainer") {
    return { ...DEFAULT_ENVIRONMENT, type: "apptainer", name: "bionodulo-apptainer", file: "envs/workflow.sif", image: "docker://quay.io/biocontainers/multiqc:latest", packages: [], channels: [], mounts: [".:/work"] };
  }
  return { ...DEFAULT_ENVIRONMENT };
}

function providerDefaults(provider) {
  const defaults = {
    openai: { provider: "openai", model: "gpt-4.1-mini", base_url: "" },
    "openai-compatible": { provider: "openai-compatible", model: "local-model", base_url: "http://127.0.0.1:11434/v1" },
    gemini: { provider: "gemini", model: "gemini-1.5-flash", base_url: "" },
    openrouter: { provider: "openrouter", model: "openai/gpt-4.1-mini", base_url: "" },
  };
  return defaults[provider] || defaults.openai;
}

function providerLabel(provider) {
  return {
    openai: "OpenAI",
    "openai-compatible": "OpenAI-compatible",
    gemini: "Gemini",
    openrouter: "OpenRouter",
  }[provider] || provider;
}

function loadLlmSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem("bionodulo.llm.settings") || "{}");
    return { ...DEFAULT_LLM_SETTINGS, ...saved, api_key: localStorage.getItem("bionodulo.llm.api_key") || "" };
  } catch {
    return { ...DEFAULT_LLM_SETTINGS };
  }
}

function loadThemePreference() {
  const value = localStorage.getItem("bionodulo.theme") || "system";
  return ["system", "dark", "light"].includes(value) ? value : "system";
}

function loadConfirmFileDelete() {
  return localStorage.getItem("bionodulo.confirm_file_delete") !== "0";
}

function persistLlmSettings(settings) {
  try {
    const { api_key, ...safeSettings } = settings;
    localStorage.setItem("bionodulo.llm.settings", JSON.stringify(safeSettings));
    if (api_key) localStorage.setItem("bionodulo.llm.api_key", api_key);
    else localStorage.removeItem("bionodulo.llm.api_key");
  } catch {
    // Ignore storage failures; chat still works with in-memory settings.
  }
}

function workflowPreviewModel(currentWorkflow, proposedWorkflow) {
  const currentNodes = new Map((currentWorkflow?.nodes || []).map((node) => [node.id, node]));
  const proposedNodes = new Map((proposedWorkflow?.nodes || []).map((node) => [node.id, node]));
  const allIds = Array.from(new Set([...currentNodes.keys(), ...proposedNodes.keys()]));
  const currentEdgeIds = new Set((currentWorkflow?.edges || []).map(edgeKey));
  const proposedEdges = (proposedWorkflow?.edges || []).map((edge) => ({ ...edge, status: currentEdgeIds.has(edgeKey(edge)) ? "same" : "new" }));
  const proposedEdgeIds = new Set(proposedEdges.map(edgeKey));
  const deletedEdges = (currentWorkflow?.edges || []).filter((edge) => !proposedEdgeIds.has(edgeKey(edge))).map((edge) => ({ ...edge, status: "deleted" }));
  const previewEdges = [...proposedEdges, ...deletedEdges];
  const layout = previewLayout(allIds, previewEdges);
  const nodes = allIds.map((id, index) => {
    const current = currentNodes.get(id);
    const proposed = proposedNodes.get(id);
    const source = proposed || current;
    const status = !proposed ? "deleted" : !current ? "new" : comparableNode(current) === comparableNode(proposed) ? "same" : "edited";
    const point = layout.get(id) || { x: index, y: 0 };
    return {
      id,
      position: { x: point.x * 210, y: point.y * 95 },
      width: 150,
      height: 58,
      data: {
        label: id.length > 18 ? `${id.slice(0, 15)}...` : id,
        type: source.type || "node",
        status,
      },
    };
  });
  return { nodes };
}

function workflowOverviewModel(nodes) {
  const width = 640;
  const height = 200;
  const padding = 30;
  if (!nodes.length) return { width, height, nodes: [] };
  const sourceNodes = nodes.map((node) => ({
    id: node.id,
    status: node.data?.status || "same",
    x: node.position?.x || 0,
    y: node.position?.y || 0,
    width: node.width || 150,
    height: node.height || 58,
  }));
  const bounds = sourceNodes.reduce((acc, node) => ({
    minX: Math.min(acc.minX, node.x),
    minY: Math.min(acc.minY, node.y),
    maxX: Math.max(acc.maxX, node.x + node.width),
    maxY: Math.max(acc.maxY, node.y + node.height),
  }), { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity });
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanY = Math.max(1, bounds.maxY - bounds.minY);
  const scale = Math.min((width - padding * 2) / spanX, (height - padding * 2) / spanY, 0.42);
  const graphWidth = spanX * scale;
  const graphHeight = spanY * scale;
  const offsetX = (width - graphWidth) / 2;
  const offsetY = (height - graphHeight) / 2;
  return {
    width,
    height,
    nodes: sourceNodes.map((node) => ({
      id: node.id,
      status: node.status,
      x: offsetX + (node.x - bounds.minX) * scale,
      y: offsetY + (node.y - bounds.minY) * scale,
      width: Math.max(18, node.width * scale),
      height: Math.max(12, node.height * scale),
    })),
  };
}

function previewLayout(ids, edges) {
  const known = new Set(ids);
  const incoming = new Map(ids.map((id) => [id, 0]));
  const outgoing = new Map(ids.map((id) => [id, []]));
  for (const edge of edges) {
    const from = edgeFrom(edge).node;
    const to = edgeTo(edge).node;
    if (!known.has(from) || !known.has(to)) continue;
    outgoing.get(from).push(to);
    incoming.set(to, (incoming.get(to) || 0) + 1);
  }
  const queue = ids.filter((id) => (incoming.get(id) || 0) === 0);
  const depth = new Map(queue.map((id) => [id, 0]));
  while (queue.length) {
    const id = queue.shift();
    const nextDepth = (depth.get(id) || 0) + 1;
    for (const next of outgoing.get(id) || []) {
      depth.set(next, Math.max(depth.get(next) || 0, nextDepth));
      incoming.set(next, (incoming.get(next) || 0) - 1);
      if (incoming.get(next) === 0) queue.push(next);
    }
  }
  ids.forEach((id, index) => {
    if (!depth.has(id)) depth.set(id, index);
  });
  const columns = new Map();
  for (const id of ids) {
    const x = depth.get(id) || 0;
    columns.set(x, [...(columns.get(x) || []), id]);
  }
  const points = new Map();
  for (const [x, columnIds] of columns.entries()) {
    columnIds.forEach((id, y) => points.set(id, { x, y }));
  }
  return points;
}

function comparableNode(node) {
  return JSON.stringify({ type: node.type, params: node.params || {}, position: node.position || {} });
}

function edgeKey(edge) {
  const from = edgeFrom(edge);
  const to = edgeTo(edge);
  return `${from.node}:${from.output}->${to.node}:${to.input}`;
}

function edgeFrom(edge) {
  return edge?.from || edge?.from_ || {};
}

function edgeTo(edge) {
  return edge?.to || {};
}

function nodeInfoForWorkflow(node) {
  const meta = node.data?.meta || {};
  return {
    display_name: meta.display_name || node.data?.type,
    category: meta.category || "Unknown",
    version: meta.version || "0.1.0",
    documentation_url: meta.documentation_url || null,
    custom_node: Boolean(meta.custom_node),
    package: meta.package || (meta.custom_node ? meta.category : "bionodulo-core"),
    github_url: meta.github_url || meta.source_url || null,
    requires_external_tools: Boolean(meta.requires_external_tools),
    required_executables: meta.required_executables || [],
    environment: meta.environment || null,
  };
}

function workflowDependencies(workflowNodes, environmentSpec) {
  const tools = Array.from(new Set(workflowNodes.flatMap((node) => node.node_info?.required_executables || []))).sort();
  const nodeTypes = Array.from(new Set(workflowNodes.map((node) => node.type))).sort();
  const nodePackages = Array.from(new Set(workflowNodes.map((node) => node.node_info?.package).filter(Boolean))).sort();
  return {
    schema_version: "0.1.0",
    node_types: nodeTypes,
    node_packages: nodePackages.map((name) => ({ name, version: name === "bionodulo-core" ? "0.1.0" : "unknown" })),
    external_tools: tools.map((name) => ({ name, version: "unknown", executable: name })),
    environment: {
      type: environmentSpec.type,
      name: environmentSpec.name,
      file: environmentSpec.file || null,
      image: environmentSpec.image || null,
      channels: environmentSpec.channels || [],
      packages: environmentSpec.packages || [],
      pip: environmentSpec.pip || [],
      mounts: environmentSpec.mounts || [],
      notes: environmentSpec.notes || "",
    },
  };
}

function edgeColorForSource(source, output) {
  const key = `${source || ""}:${output || ""}`;
  let hash = 0;
  for (let index = 0; index < key.length; index += 1) hash = (hash * 31 + key.charCodeAt(index)) >>> 0;
  return EDGE_PALETTE[hash % EDGE_PALETTE.length];
}

function miniMapNodeColor(node, selectedNodeId = null) {
  const status = selectedNodeId && node.id === selectedNodeId ? "selected" : node.data?.status || "idle";
  return {
    selected: "#38bdf8",
    edited: "#f59e0b",
    new: "#22c55e",
    deleted: "#ef4444",
    running: "#22c55e",
    failed: "#ef4444",
    invalid: "#ef4444",
    completed: "#14b8a6",
    cached: "#60a5fa",
    queued: "#f59e0b",
    interrupted: "#94a3b8",
    blocked: "#94a3b8",
  }[status] || "#64748b";
}

function miniMapNodeStrokeColor(node, selectedNodeId = null) {
  const status = selectedNodeId && node.id === selectedNodeId ? "selected" : node.data?.status || "idle";
  return {
    selected: "#e0f2fe",
    edited: "#ffedd5",
    new: "#dcfce7",
    deleted: "#fee2e2",
    running: "#bbf7d0",
    failed: "#fecaca",
    invalid: "#fecaca",
    completed: "#ccfbf1",
    cached: "#dbeafe",
    queued: "#fed7aa",
    interrupted: "#e2e8f0",
    blocked: "#e2e8f0",
  }[status] || "#cbd5e1";
}

function lines(value) {
  return String(value).split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean);
}

function flattenFiles(item, result = []) {
  if (!item) return result;
  if (item.type === "file") result.push(item);
  for (const child of item.children || []) flattenFiles(child, result);
  return result;
}

function fileKind(item) {
  const name = (item?.name || "").toLowerCase();
  const path = (item?.path || "").toLowerCase();
  if (path.endsWith(".bionodulo.json") || path.endsWith(".json") && path.includes("workflow")) return "workflow";
  if (name.endsWith(".fastq") || name.endsWith(".fastq.gz") || name.endsWith(".fq") || name.endsWith(".fq.gz") || name.endsWith(".fasta") || name.endsWith(".fa")) return "sequence";
  if (name.endsWith(".bam") || name.endsWith(".sam") || name.endsWith(".cram") || name.endsWith(".bai")) return "alignment";
  if (name.endsWith(".vcf") || name.endsWith(".vcf.gz") || name.endsWith(".bcf")) return "variant";
  if (name.endsWith(".html") || name.endsWith(".log") || name.endsWith(".txt") || path.includes("/reports/") || path.includes("multiqc") || path.includes("fastqc")) return "report";
  if (name.endsWith(".csv") || name.endsWith(".tsv")) return "table";
  return "file";
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function GroupContextMenu({ menu, group, onRename, onSetColor, onDelete, onToggleCollapsed, onClose }) {
  if (!group) return null;
  const style = {
    left: clamp(menu.x, 12, window.innerWidth - 300),
    top: clamp(menu.y, 70, window.innerHeight - 400),
  };
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState(group.name);
  const inputRef = useRef(null);

  useEffect(() => {
    if (renaming && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [renaming]);

  function commitRename() {
    const trimmed = nameDraft.trim();
    if (trimmed && trimmed !== group.name) {
      onRename(trimmed);
    }
    setRenaming(false);
  }

  return h("div", { className: "node-menu group-menu", style, onClick: (event) => event.stopPropagation(), onContextMenu: (event) => event.preventDefault() },
    h("div", { className: "context-head" },
      renaming ? h("input", {
        ref: inputRef,
        className: "group-rename-input",
        value: nameDraft,
        onChange: (event) => setNameDraft(event.target.value),
        onBlur: commitRename,
        onKeyDown: (event) => {
          if (event.key === "Enter") commitRename();
          if (event.key === "Escape") { setNameDraft(group.name); setRenaming(false); }
        },
      }) : h("strong", null, group.name),
      h("button", { onClick: onClose, title: "Close menu" }, "x"),
    ),
    h("div", { className: "node-menu-section" },
      h("button", { className: "node-menu-item", onClick: () => { setRenaming(true); setNameDraft(group.name); } },
        h(Icon, { name: "edit" }),
        h("span", null, "Rename"),
      ),
      h("button", { className: "node-menu-item", onClick: () => { onToggleCollapsed(group.id); onClose(); } },
        h(Icon, { name: group.collapsed ? "fit" : "nodes" }),
        h("span", null, group.collapsed ? "Expand Group" : "Collapse Group"),
      ),
    ),
    h("div", { className: "node-menu-divider" }),
    h("div", { className: "group-color-picker" },
      h("span", { className: "group-color-label" }, "Color"),
      h("div", { className: "group-color-swatches" },
        GROUP_COLORS.map((color) => h("button", {
          key: color,
          className: `group-color-swatch ${group.color === color ? "active" : ""}`,
          style: { background: color },
          onClick: () => onSetColor(color),
          title: color,
        })),
      ),
    ),
    h("div", { className: "node-menu-divider" }),
    h("div", { className: "node-menu-section" },
      h("button", { className: "node-menu-item node-menu-danger", onClick: onDelete },
        h(Icon, { name: "trash" }),
        h("span", null, "Remove Group"),
      ),
    ),
  );
}

createRoot(document.getElementById("root")).render(h(App));
