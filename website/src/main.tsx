import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import './styles.css';

type IconName =
  | 'node'
  | 'cube'
  | 'template'
  | 'grid'
  | 'server'
  | 'play'
  | 'users'
  | 'lock'
  | 'eye'
  | 'flask'
  | 'gift'
  | 'license'
  | 'building'
  | 'github'
  | 'discord'
  | 'linkedin'
  | 'mail'
  | 'arrow'
  | 'check'
  | 'code';

type ToolLogoName =
  | 'python'
  | 'r'
  | 'conda'
  | 'slurm'
  | 'pbs'
  | 'sge'
  | 'snakemake'
  | 'nextflow'
  | 'cwl'
  | 'galaxy'
  | 'chatgpt'
  | 'claude'
  | 'openrouter';

const stats = [
  { value: '94', label: 'Bioinformatics Nodes', detail: 'Registered node types in the app', icon: 'cube' },
  { value: '13', label: 'Workflow Templates', detail: 'Built-in analysis starting points', icon: 'template' },
  { value: '19', label: 'Node Categories', detail: 'QC, RNA-seq, variant calling, and more', icon: 'grid' },
  { value: '3', label: 'HPC Schedulers', detail: 'SLURM, PBS/Torque, and SGE', icon: 'server' },
] as const;

const featureTabs = [
  {
    title: 'Visual Workflow Builder',
    kicker: 'Design pipelines without losing the science',
    text: 'Build reproducible bioinformatics workflows as a node graph, inspect every step, and keep local execution close at hand.',
    bullets: ['Drag nodes onto a canvas and connect typed inputs', 'Start from 13 built-in workflow templates', 'Inspect parameters, status, and outputs in one place'],
    icon: 'node',
  },
  {
    title: 'Collaboration and HPC',
    kicker: 'Work locally first, scale when needed',
    text: 'Keep solo workflows private by default, then enable collaboration or cluster execution for the projects that need it.',
    bullets: ['Optional shared editing, comments, versions, and audit history', 'Local mode remains the default for individual research', 'Configure SLURM, PBS/Torque, or SGE for HPC runs'],
    icon: 'users',
  },
  {
    title: 'Local-first',
    kicker: 'Private by default',
    text: 'BioNodulo runs locally by default. Your data never leaves your machine unless you choose to share it.',
    bullets: ['Run workflows offline on your own computer', 'Keep templates and workflow state available locally', 'Enable collaboration only when you are ready'],
    icon: 'lock',
  },
  {
    title: 'AI Assistant',
    kicker: 'A helper that understands the workflow',
    text: 'Use the built-in assistant to inspect graphs, add nodes, validate connections, and draft changes for review.',
    bullets: ['Ask questions about the current workflow state', 'Create nodes and edges through tool-backed actions', 'Validate configuration before expensive runs'],
    icon: 'code',
  },
] as const;

const integrations: Array<{ name: string; logo: ToolLogoName }> = [
  { name: 'Python', logo: 'python' },
  { name: 'R', logo: 'r' },
  { name: 'Conda / Mamba', logo: 'conda' },
  { name: 'SLURM', logo: 'slurm' },
  { name: 'PBS / Torque', logo: 'pbs' },
  { name: 'SGE', logo: 'sge' },
  { name: 'Snakemake', logo: 'snakemake' },
  { name: 'Nextflow', logo: 'nextflow' },
  { name: 'CWL', logo: 'cwl' },
  { name: 'Galaxy', logo: 'galaxy' },
  { name: 'ChatGPT', logo: 'chatgpt' },
  { name: 'Claude', logo: 'claude' },
  { name: 'OpenRouter', logo: 'openrouter' },
];

const outerIntegrations = integrations.slice(0, 7);
const innerIntegrations = integrations.slice(7);

const licensing = [
  {
    title: 'Open Beta',
    text: 'BioNodulo is currently in open beta while features and workflows are refined with user feedback.',
    icon: 'flask',
  },
  {
    title: 'Free for Research',
    text: 'Open-source and free to use for academic and non-commercial research work.',
    icon: 'gift',
  },
  {
    title: 'Publishing License',
    text: 'A paid license is required for commercial use or publishing results produced with BioNodulo.',
    icon: 'license',
  },
  {
    title: 'Institutional Pricing',
    text: 'Institutions can contact us for licensing, deployment, and future hosted cloud options.',
    icon: 'building',
  },
] as const;

const faqs = [
  {
    question: 'Is BioNodulo free?',
    answer:
      'BioNodulo is open-source and free to use for research purposes during open beta. A paid license is required for publishing or commercial use.',
  },
  {
    question: 'Can I run it locally?',
    answer:
      'Yes. BioNodulo is local-first: workflows, templates, system stats, and execution are designed to work from a locally hosted app.',
  },
  {
    question: 'Do I need programming skills?',
    answer:
      'No programming is required for many workflows, but BioNodulo also supports command-style and scripting-oriented nodes for advanced users.',
  },
  {
    question: 'Can it run on HPC?',
    answer:
      'BioNodulo includes HPC configuration surfaces for SLURM, PBS/Torque, and SGE schedulers.',
  },
  {
    question: 'How does collaboration work?',
    answer:
      'Collaboration is optional. You can work locally by default, then enable shared editing, presence, comments, versions, and audit history when needed.',
  },
  {
    question: 'Are hosted cloud services available?',
    answer:
      'Hosted services are planned for the future. Pricing will be determined and is expected to include licensing plus RDP or VPS infrastructure costs.',
  },
];

function NoiseGradientBackground() {
  return (
    <svg className="noise-gradient-bg" viewBox="0 0 1440 1200" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="bioNoiseBase" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#071018" />
          <stop offset="48%" stopColor="#0f172a" />
          <stop offset="100%" stopColor="#05070d" />
        </linearGradient>
        <radialGradient id="bioTealBlob" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#2dd4bf" stopOpacity="0.98" />
          <stop offset="46%" stopColor="#0ea5e9" stopOpacity="0.44" />
          <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="bioGreenBlob" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.82" />
          <stop offset="54%" stopColor="#2dd4bf" stopOpacity="0.32" />
          <stop offset="100%" stopColor="#2dd4bf" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="bioBlueBlob" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.72" />
          <stop offset="58%" stopColor="#334155" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#334155" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="bioAmberBlob" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffc85f" stopOpacity="0.48" />
          <stop offset="60%" stopColor="#22c55e" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </radialGradient>
        <filter id="bioGradientNoise" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.011 0.019" numOctaves="3" seed="17" result="noise">
            <animate attributeName="baseFrequency" dur="9s" values="0.011 0.019;0.019 0.012;0.014 0.024;0.011 0.019" repeatCount="indefinite" />
          </feTurbulence>
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="48" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="bioWireNoise" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.018 0.03" numOctaves="2" seed="23" result="wireNoise">
            <animate attributeName="baseFrequency" dur="7s" values="0.018 0.03;0.03 0.018;0.02 0.026;0.018 0.03" repeatCount="indefinite" />
          </feTurbulence>
          <feDisplacementMap in="SourceGraphic" in2="wireNoise" scale="22" />
        </filter>
        <filter id="bioFineGrain">
          <feTurbulence type="fractalNoise" baseFrequency="0.78" numOctaves="2" seed="9" result="grain" />
          <feColorMatrix in="grain" type="saturate" values="0" />
          <feComponentTransfer>
            <feFuncA type="table" tableValues="0 0.19" />
          </feComponentTransfer>
        </filter>
        <pattern id="bioWirePattern" width="74" height="74" patternUnits="userSpaceOnUse">
          <path d="M74 0H0V74" />
          <path d="M0 74L74 0" />
          <path d="M37 0V74M0 37H74" className="wire-minor" />
        </pattern>
      </defs>
      <rect width="1440" height="1200" fill="url(#bioNoiseBase)" />
      <g className="noise-gradient-field" filter="url(#bioGradientNoise)">
        <ellipse className="noise-blob noise-blob-main" cx="910" cy="230" rx="540" ry="330" fill="url(#bioTealBlob)" />
        <ellipse className="noise-blob noise-blob-blue" cx="330" cy="400" rx="330" ry="260" fill="url(#bioBlueBlob)" />
        <ellipse className="noise-blob noise-blob-green" cx="1050" cy="800" rx="410" ry="310" fill="url(#bioGreenBlob)" />
        <ellipse className="noise-blob noise-blob-amber" cx="470" cy="960" rx="280" ry="220" fill="url(#bioAmberBlob)" />
      </g>
      <g className="noise-gradient-wire" filter="url(#bioWireNoise)">
        <rect width="1440" height="1200" fill="url(#bioWirePattern)" />
      </g>
      <rect className="noise-gradient-grain" width="1440" height="1200" filter="url(#bioFineGrain)" />
      <rect className="noise-gradient-vignette" width="1440" height="1200" />
    </svg>
  );
}

function Icon({ name }: { name: IconName }) {
  const common = {
    width: 24,
    height: 24,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  };

  switch (name) {
    case 'node':
      return <svg {...common}><circle cx="5" cy="12" r="3" /><circle cx="19" cy="6" r="3" /><circle cx="19" cy="18" r="3" /><path d="M8 11l8-4M8 13l8 4" /></svg>;
    case 'cube':
      return <svg {...common}><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" /><path d="M4 7.5l8 4.5 8-4.5M12 12v9" /></svg>;
    case 'template':
      return <svg {...common}><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v5h5M10 13h6M10 17h4" /></svg>;
    case 'grid':
      return <svg {...common}><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" /></svg>;
    case 'server':
      return <svg {...common}><rect x="4" y="4" width="16" height="6" rx="2" /><rect x="4" y="14" width="16" height="6" rx="2" /><path d="M8 7h.01M8 17h.01M12 7h4M12 17h4" /></svg>;
    case 'play':
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M10 8l6 4-6 4z" fill="currentColor" stroke="none" /></svg>;
    case 'users':
      return <svg {...common}><circle cx="9" cy="8" r="3" /><circle cx="17" cy="10" r="2.5" /><path d="M3.5 20a5.5 5.5 0 0111 0M14 20a4 4 0 017 0" /></svg>;
    case 'lock':
      return <svg {...common}><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 018 0v3" /></svg>;
    case 'eye':
      return <svg {...common}><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z" /><circle cx="12" cy="12" r="3" /></svg>;
    case 'flask':
      return <svg {...common}><path d="M9 3h6M10 3v5l-5 9a3 3 0 002.6 4.5h8.8A3 3 0 0019 17l-5-9V3" /><path d="M8 15h8" /></svg>;
    case 'gift':
      return <svg {...common}><path d="M4 11h16v9H4zM3 7h18v4H3zM12 7v13M12 7C9 7 7 5.7 7 4.3 7 3.5 7.7 3 8.6 3 10.5 3 12 7 12 7zM12 7s1.5-4 3.4-4c.9 0 1.6.5 1.6 1.3C17 5.7 15 7 12 7z" /></svg>;
    case 'license':
      return <svg {...common}><path d="M7 3h10v18l-5-3-5 3z" /><path d="M10 8h4M10 12h4" /></svg>;
    case 'building':
      return <svg {...common}><path d="M4 21h16M6 21V5l8-3 4 2v17M9 8h.01M13 8h.01M9 12h.01M13 12h.01M9 16h.01M13 16h.01" /></svg>;
    case 'github':
      return <svg {...common}><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.9a3.4 3.4 0 00-1-2.6c3.3-.4 6.8-1.6 6.8-7.3A5.7 5.7 0 0020 4.2 5.3 5.3 0 0019.9 0S18.4-.4 15 1.7a17.4 17.4 0 00-8 0C3.6-.4 2.1 0 2.1 0A5.3 5.3 0 002 4.2 5.7 5.7 0 00.2 8.2c0 5.7 3.5 6.9 6.8 7.3a3.4 3.4 0 00-1 2.6V22" transform="translate(1 1) scale(.9)" /></svg>;
    case 'discord':
      return <svg {...common}><path d="M8 8a10 10 0 018 0M7 17c-2 0-3-1-3-1 .2-5 2-9 2-9a10 10 0 013-1l.5 1M17 17c2 0 3-1 3-1-.2-5-2-9-2-9a10 10 0 00-3-1l-.5 1M9 14h.01M15 14h.01" /></svg>;
    case 'linkedin':
      return <svg {...common}><path d="M4 9h4v11H4zM4 4h4v3H4zM11 9h4v2a4 4 0 014-2c2.2 0 3 1.3 3 4v7h-4v-6c0-1.2-.4-2-1.5-2S15 12.8 15 14v6h-4z" /></svg>;
    case 'mail':
      return <svg {...common}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M4 7l8 6 8-6" /></svg>;
    case 'arrow':
      return <svg {...common}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
    case 'check':
      return <svg {...common}><path d="M20 6L9 17l-5-5" /></svg>;
    case 'code':
      return <svg {...common}><path d="M8 9l-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" /></svg>;
  }
}

function Logo() {
  return (
    <a className="logo" href="/">
      <LogoMark />
      <span>BioNodulo</span>
    </a>
  );
}

function LogoMark() {
  return (
    <svg className="logo-mark" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="18" fill="#111314" />
      <circle cx="19" cy="22" r="7" fill="#7ee6b4" />
      <circle cx="45" cy="20" r="7" fill="#d7f36b" />
      <circle cx="32" cy="44" r="8" fill="#8fb7ff" />
      <path d="M25 22h13M23 28l6 10M41 27l-6 11" stroke="#f5f1e8" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function Header() {
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let previousY = window.scrollY;

    const handleScroll = () => {
      const nextY = window.scrollY;
      setHidden(nextY > 120 && nextY > previousY);
      previousY = nextY;
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header className={`site-header ${hidden ? 'is-hidden' : ''}`}>
      <Logo />
      <nav aria-label="Primary navigation">
        <a href="/features">Features</a>
        <a href="/download">Download</a>
        <a href="/pricing">Pricing</a>
        <a href="/contact">Contact</a>
      </nav>
      <div className="header-actions">
        <a className="button secondary small" href="https://github.com/Classacre/BioNodulo" target="_blank" rel="noreferrer">
          <Icon name="github" />
          GitHub
        </a>
        <a className="button primary small" href="/demo">
          View Demo
        </a>
      </div>
    </header>
  );
}

function ProductMockup({ compact = false, hero = false, style }: { compact?: boolean; hero?: boolean; style?: React.CSSProperties }) {
  const nodes = [
    { label: 'Input FASTQ', x: 15, y: 42, color: 'blue' },
    { label: 'FastQC', x: 41, y: 27, color: 'amber' },
    { label: 'Trim Reads', x: 62, y: 42, color: 'violet' },
    { label: 'STAR Align', x: 43, y: 63, color: 'cyan' },
    { label: 'DESeq2', x: 69, y: 64, color: 'green' },
  ];

  return (
    <div className={`product-mockup ${compact ? 'compact' : ''} ${hero ? 'hero-mockup' : ''}`} style={style} aria-label="BioNodulo workflow editor preview">
      <div className="mockup-toolbar">
        <div className="window-dots"><span /><span /><span /></div>
        <span>RNA-seq Differential Expression</span>
        <div className="mockup-tools"><span /><span /><span /></div>
        <button>Run</button>
      </div>
      <div className="mockup-body">
        <aside>
          {['Data', 'QC', 'Alignment', 'RNA-seq', 'R', 'Templates'].map(item => <span key={item}>{item}</span>)}
        </aside>
        <div className="graph">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <path d="M25 49 C34 49 33 34 41 34" />
            <path d="M51 34 C59 34 57 48 62 48" />
            <path d="M25 49 C34 49 33 68 43 68" />
            <path d="M53 68 C63 68 61 67 69 67" />
          </svg>
          {nodes.map(node => (
            <div className={`graph-node ${node.color}`} style={{ left: `${node.x}%`, top: `${node.y}%` }} key={node.label}>
              {node.label}
            </div>
          ))}
        </div>
        <aside className="details">
          <strong>Node Details</strong>
          <label>Reference Genome</label>
          <span>GRCh38</span>
          <label>Threads</label>
          <span>16</span>
          <label>Status</label>
          <span className="ready">Ready</span>
        </aside>
      </div>
    </div>
  );
}

function Hero() {
  const [tiltProgress, setTiltProgress] = useState(0);

  useEffect(() => {
    const updateTilt = () => {
      setTiltProgress(Math.min(1, window.scrollY / 420));
    };

    updateTilt();
    window.addEventListener('scroll', updateTilt, { passive: true });
    return () => window.removeEventListener('scroll', updateTilt);
  }, []);

  const tilt = 58 * (1 - tiltProgress);
  const lift = 58 * (1 - tiltProgress);
  const scale = 1.04 - 0.04 * tiltProgress;

  return (
    <section className="hero">
      <div className="hero-copy">
        <span className="beta">Open Beta</span>
        <h1>Visual bioinformatics pipelines, <br /><span>node by node.</span></h1>
        <p>
          Build, run, and share reproducible research workflows with 94 bioinformatics nodes, 13 templates,
          local-first execution, optional collaboration, and HPC support.
        </p>
        <div className="hero-actions">
          <a className="button primary" href="/demo">View Demo <Icon name="arrow" /></a>
          <a className="button secondary" href="https://github.com/Classacre/BioNodulo" target="_blank" rel="noreferrer"><Icon name="github" /> GitHub</a>
        </div>
        <div className="trust-line">
          <span>Open Source</span>
          <span>Local-First</span>
          <span>Cross Platform</span>
          <span>Python Powered</span>
        </div>
      </div>
      <ProductMockup
        hero
        style={{ transform: `translateY(${lift}px) rotateX(${tilt}deg) rotateZ(${-2 * (1 - tiltProgress)}deg) scale(${scale})` }}
      />
    </section>
  );
}

function Stats() {
  return (
    <section className="stats reveal" aria-label="BioNodulo product statistics">
      {stats.map(stat => (
        <div className="stat pop-in" key={stat.label}>
          <Icon name={stat.icon} />
          <strong>{stat.value}</strong>
          <span>{stat.label}</span>
          <small>{stat.detail}</small>
        </div>
      ))}
    </section>
  );
}

function Features() {
  const [activeTab, setActiveTab] = useState(0);
  const activeFeature = featureTabs[activeTab];

  return (
    <section className="section reveal" id="features">
      <div className="section-heading">
        <h2>Everything you need to do more research</h2>
        <p>BioNodulo keeps the workflow visible while still leaving room for serious local, HPC, and collaborative execution.</p>
      </div>
      <div className="feature-tabs" role="tablist" aria-label="BioNodulo feature areas">
        {featureTabs.map((feature, index) => (
          <button
            className={`pop-in ${activeTab === index ? 'active' : ''}`}
            type="button"
            role="tab"
            aria-selected={activeTab === index}
            key={feature.title}
            onClick={() => setActiveTab(index)}
          >
            <Icon name={feature.icon} />
            {feature.title}
          </button>
        ))}
      </div>
      <div className="feature-panel pop-in">
        <article>
          <span className="section-label">{activeFeature.kicker}</span>
          <h3>{activeFeature.title}</h3>
          <p>{activeFeature.text}</p>
          <ul>
            {activeFeature.bullets.map(bullet => (
              <li key={bullet}><Icon name="check" /> {bullet}</li>
            ))}
          </ul>
        </article>
        <FeatureScreenshot feature={activeFeature.title} />
      </div>
    </section>
  );
}

function FeatureScreenshot({ feature }: { feature: string }) {
  if (feature === 'Collaboration and HPC') {
    return (
      <div className="feature-shot collaboration-shot" aria-label="Collaboration and HPC preview">
        <div className="shot-toolbar"><span /><strong>Shared RNA-seq Project</strong><em>Live</em></div>
        <div className="collab-grid">
          <div className="collab-card">
            <h4>Presence</h4>
            <div className="avatars"><span>M</span><span>A</span><span>L</span></div>
            <p>3 collaborators reviewing the workflow</p>
          </div>
          <div className="collab-card">
            <h4>HPC Queue</h4>
            <div className="queue-row"><b>SLURM</b><span>Running</span></div>
            <div className="queue-row"><b>PBS</b><span>Ready</span></div>
            <div className="queue-row"><b>SGE</b><span>Configured</span></div>
          </div>
        </div>
      </div>
    );
  }

  if (feature === 'AI Assistant') {
    return (
      <div className="feature-shot assistant-shot" aria-label="AI Assistant preview">
        <div className="shot-toolbar"><span /><strong>BioNodulo Assistant</strong><em>Tools enabled</em></div>
        <div className="assistant-thread">
          <p>Inspect the workflow and suggest missing QC steps.</p>
          <div>
            <Icon name="code" />
            <span>Added FastQC before trimming and validated downstream edges.</span>
          </div>
          <button type="button">Review Changes</button>
        </div>
      </div>
    );
  }

  if (feature === 'Local-first') {
    return (
      <div className="feature-shot local-shot" aria-label="Local-first preview">
        <div className="shot-toolbar"><span /><strong>Local Runtime</strong><em>Offline</em></div>
        <div className="local-grid">
          <div className="system-panel">
            <h3>System Stats</h3>
            <div><span>CPU</span><i style={{ width: '28%' }} /></div>
            <div><span>Memory</span><i style={{ width: '54%' }} /></div>
            <div><span>Disk</span><i style={{ width: '73%' }} /></div>
            <div><span>Processes</span><b>182</b></div>
          </div>
          <div className="system-panel">
            <h3>Recent Runs</h3>
            {['FASTQ QC Workflow', 'Variant Calling Pipeline', 'Metagenomics Analysis'].map(name => (
              <div className="run-row" key={name}><Icon name="check" /><span>{name}</span></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="feature-shot workflow-shot" aria-label="Visual workflow builder preview">
      <ProductMockup compact />
    </div>
  );
}

function Integrations() {
  return (
    <section className="section compact reveal" id="integrations">
      <div className="section-heading">
        <h2>Works with the tools you already use</h2>
        <p>BioNodulo stays close to the open research stack, from scripting languages to workflow engines and HPC schedulers.</p>
      </div>
      <div className="integration-orbit" aria-label="BioNodulo integrations">
        <div className="orbit-ring outer" />
        <div className="orbit-ring inner" />
        <div className="orbit-core">
          <LogoMark />
          <span>BioNodulo</span>
        </div>
        <div className="integration-track outer-track">
          {outerIntegrations.map((item, index) => (
            <div className="integration" style={{ '--i': index } as React.CSSProperties} aria-label={item.name} key={item.name}>
              <ToolLogo name={item.logo} />
            </div>
          ))}
        </div>
        <div className="integration-track inner-track">
          {innerIntegrations.map((item, index) => (
            <div className="integration" style={{ '--i': index } as React.CSSProperties} aria-label={item.name} key={item.name}>
              <ToolLogo name={item.logo} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ToolLogo({ name }: { name: ToolLogoName }) {
  switch (name) {
    case 'python':
      return <svg viewBox="0 0 48 48"><path fill="#3776ab" d="M24 4c-8 0-8 4-8 4v5h9v2H12s-6 0-6 9 5 9 5 9h3v-5s0-5 5-5h10s5 0 5-5V9s0-5-10-5z" /><path fill="#ffd43b" d="M24 44c8 0 8-4 8-4v-5h-9v-2h13s6 0 6-9-5-9-5-9h-3v5s0 5-5 5H19s-5 0-5 5v9s0 5 10 5z" /><circle cx="20" cy="10" r="1.8" fill="#fff" /><circle cx="28" cy="38" r="1.8" fill="#7a5b00" /></svg>;
    case 'r':
      return <svg viewBox="0 0 48 48"><ellipse cx="24" cy="24" rx="20" ry="14" fill="#d7deea" /><ellipse cx="24" cy="24" rx="15" ry="9" fill="#276dc3" /><path fill="#fff" d="M15 18h12c5 0 8 2 8 6 0 2.5-1.4 4.2-4 5.1l5 7h-8l-4-6h-3v6h-6zm6 8h5c2 0 3-.6 3-2s-1-2-3-2h-5z" /></svg>;
    case 'conda':
      return <svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="19" fill="#43b02a" /><path d="M15 29c5-15 17-16 20-8-8-3-14 2-17 11zm-1-8c3-6 9-9 15-8-8-4-17-.5-18 8zm16 10c-5 5-13 4-17-2 7 3 12 2 17-2z" fill="#0b1b0c" /></svg>;
    case 'slurm':
      return <svg viewBox="0 0 48 48"><rect x="8" y="9" width="32" height="30" rx="8" fill="#19a7e0" /><path d="M13 31c9-15 14-15 22 0M17 20h14M17 25h14" stroke="#fff" strokeWidth="3" strokeLinecap="round" fill="none" /></svg>;
    case 'pbs':
      return <svg viewBox="0 0 48 48"><rect x="7" y="10" width="34" height="28" rx="7" fill="#f05a28" /><path d="M15 30V18h9c4 0 6 2 6 5s-2 5-6 5h-4v2zm5-7h4M31 18h3v12h-3" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" /></svg>;
    case 'sge':
      return <svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="18" fill="#8dd63f" /><path d="M15 31c6 4 18 3 18-4 0-8-17-3-17-10 0-6 10-7 17-3" stroke="#17230f" strokeWidth="4" strokeLinecap="round" fill="none" /></svg>;
    case 'snakemake':
      return <svg viewBox="0 0 48 48"><rect x="8" y="8" width="32" height="32" rx="9" fill="#76b900" /><path d="M14 28c5 7 19 7 20 0 1-8-18-2-18-10 0-6 12-7 18-1" stroke="#fff" strokeWidth="4" strokeLinecap="round" fill="none" /></svg>;
    case 'nextflow':
      return <svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="19" fill="#00b8b0" /><path d="M15 34V14l18 20V14" stroke="#082e31" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" fill="none" /></svg>;
    case 'cwl':
      return <svg viewBox="0 0 48 48"><rect x="7" y="10" width="34" height="28" rx="7" fill="#7b61ff" /><path d="M17 18h-3a5 5 0 000 10h3M21 18l3 10 3-10M32 18v10h5" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" /></svg>;
    case 'galaxy':
      return <svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="18" fill="#ffd166" /><path d="M24 11l3.8 8 8.7 1.2-6.3 6.1 1.5 8.6L24 30.8l-7.7 4.1 1.5-8.6-6.3-6.1 8.7-1.2z" fill="#5c4b9b" /></svg>;
    case 'chatgpt':
      return <svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="19" fill="#10a37f" /><path d="M18 15c2-5 9-5 12-1 5 0 8 6 5 10 2 5-2 10-7 10-3 4-10 4-12 0-5 0-8-6-5-10-2-4 1-9 7-9zm1 6l9-5m-8 17v-9m9 8l-9-5m-1-12l8 5m2 12v-9m-9 1l9 5" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" /></svg>;
    case 'claude':
      return <svg viewBox="0 0 48 48"><rect x="6" y="6" width="36" height="36" rx="12" fill="#d97757" /><path d="M15 31l7-17h4l7 17h-4l-1.5-4h-7L19 31zm7-8h4l-2-5z" fill="#fff8ef" /></svg>;
    case 'openrouter':
      return <svg viewBox="0 0 48 48"><rect x="6" y="8" width="36" height="32" rx="10" fill="#111827" /><path d="M12 24h12m0 0l-5-5m5 5l-5 5M24 16h12M24 32h12" stroke="#7dd3fc" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /><circle cx="36" cy="16" r="3" fill="#2dd4bf" /><circle cx="36" cy="32" r="3" fill="#2dd4bf" /></svg>;
  }
}

function Licensing() {
  return (
    <section className="section reveal" id="licensing">
      <div className="section-heading">
        <h2>Open Beta. Open Source. Open for Research.</h2>
        <p>Licensing is designed around research first, with institutional and hosted options coming as the platform matures.</p>
      </div>
      <div className="license-grid">
        {licensing.map(item => (
          <article className="license-card pop-in" key={item.title}>
            <Icon name={item.icon} />
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </article>
        ))}
      </div>
      <div className="contact-strip">
        <span>Questions about licensing or institutional plans?</span>
        <a className="button primary small" href="mailto:nieuwenhuyzemikamartin@gmail.com">Contact Us</a>
      </div>
    </section>
  );
}

function DemoCallout() {
  return (
    <section className="demo-callout reveal" id="templates">
      <div>
        <span className="section-label">See BioNodulo in action</span>
        <h2>Explore BioNodulo with an interactive demo.</h2>
        <p>Try building and running a workflow in your browser. The full demo page will be added next.</p>
      </div>
      <a className="button primary" href="/demo">View Demo <Icon name="arrow" /></a>
      <ProductMockup compact />
    </section>
  );
}

function FAQ() {
  return (
    <section className="section faq reveal" id="faq">
      <div className="section-heading">
        <h2>Frequently Asked Questions</h2>
      </div>
      <div className="faq-grid">
        {faqs.map(item => (
          <details className="pop-in" key={item.question}>
            <summary>{item.question}</summary>
            <p>{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer>
      <div className="footer-brand">
        <Logo />
        <p>A visual bioinformatics workflow workbench for modern research. Open source, local-first, and built for reproducibility.</p>
        <div className="socials">
          <a href="https://github.com/Classacre/BioNodulo" aria-label="GitHub" target="_blank" rel="noreferrer"><Icon name="github" /></a>
          <a href="https://discord.gg/baNKVhZq6k" aria-label="Discord" target="_blank" rel="noreferrer"><Icon name="discord" /></a>
          <a href="https://www.linkedin.com/in/mika-nieuwenhuyzen/" aria-label="LinkedIn" target="_blank" rel="noreferrer"><Icon name="linkedin" /></a>
          <a href="mailto:nieuwenhuyzemikamartin@gmail.com" aria-label="Email"><Icon name="mail" /></a>
        </div>
      </div>
      <div className="footer-links">
        <div><strong>Product</strong><a href="/features">Features</a><a href="/download">Download</a><a href="/pricing">Pricing</a><a href="/demo">Demo</a></div>
        <div><strong>Community</strong><a href="https://github.com/Classacre/BioNodulo" target="_blank" rel="noreferrer">GitHub</a><a href="https://discord.gg/baNKVhZq6k" target="_blank" rel="noreferrer">Discord</a><a href="/contact">Contact</a></div>
        <div><strong>Company</strong><a href="/contact">Contact</a><a href="/pricing">Licensing</a><a href="https://www.linkedin.com/in/mika-nieuwenhuyzen/" target="_blank" rel="noreferrer">LinkedIn</a></div>
      </div>
      <div className="footer-bottom">
        <span>© 2026 BioNodulo</span>
        <span>Contact: nieuwenhuyzemikamartin@gmail.com</span>
      </div>
    </footer>
  );
}

function HomePage() {
  useEffect(() => {
    const targets = Array.from(document.querySelectorAll<HTMLElement>('.reveal, .pop-in'));
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) entry.target.classList.add('is-visible');
        });
      },
      { threshold: 0.16 },
    );

    targets.forEach(target => observer.observe(target));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <Header />
      <main>
        <Hero />
        <Features />
        <Stats />
        <Integrations />
        <Licensing />
        <DemoCallout />
        <FAQ />
      </main>
      <Footer />
    </>
  );
}

const detailedFeatures = [
  {
    title: 'Visual Workflow Builder',
    text: 'A LiteGraph-style canvas for turning pipelines into editable, typed workflow graphs.',
    bullets: ['Drag, connect, group, undo, redo, and inspect workflow nodes', '94 registered node types across 19 categories', 'Typed inputs, outputs, defaults, advanced parameters, and validation'],
    icon: 'node',
  },
  {
    title: 'Local Execution',
    text: 'Run locally by default with persistent workflow tabs, dependency checks, queue state, logs, previews, and cache controls.',
    bullets: ['Local workflow state persists in the browser', 'Run queue, history, node status, logs, artifacts, and image previews', 'Workflow-scoped environments and dependency resolution'],
    icon: 'play',
  },
  {
    title: 'Collaboration',
    text: 'Optional shared workspaces using Yjs sync, awareness, comments, versions, sharing, and audit history.',
    bullets: ['Collaboration stays opt-in from settings and startup choice', 'Presence cursors, active users, follow mode, and share controls', 'Comments, version history, diffs, restores, templates, and audit export'],
    icon: 'users',
  },
  {
    title: 'HPC Execution',
    text: 'Research groups can configure cluster execution while keeping local development comfortable.',
    bullets: ['SLURM, PBS/Torque, and SGE backends', 'Partition, account, modules, container, walltime, CPU, memory, and extra args', 'Status checks, job submission, job lookup, and script preview'],
    icon: 'server',
  },
  {
    title: 'AI Workflow Assistant',
    text: 'A tool-backed assistant that can reason over the active workflow and propose graph changes for review.',
    bullets: ['22 workflow-aware tools for graph, node, template, settings, and system context', 'OpenAI, Anthropic, or custom OpenAI-compatible provider settings', 'Chat sessions, attachments, pasted node selections, and review-first changes'],
    icon: 'code',
  },
] as const;

const featureAuditStats = [
  { value: '94', label: 'Built-in nodes', detail: 'Parsed from bionodulo/nodes/builtin' },
  { value: '19', label: 'Node categories', detail: 'Alignment, RNA-Seq, variant, metagenomics, and more' },
  { value: '13', label: 'Workflow templates', detail: 'Local templates available without collaboration' },
  { value: '3', label: 'HPC schedulers', detail: 'SLURM, PBS/Torque, and SGE' },
  { value: '5', label: 'Workflow formats', detail: 'BioNodulo JSON, Snakemake, Nextflow, CWL, Galaxy' },
  { value: '22', label: 'AI tools', detail: 'Tool-backed assistant actions in bionodulo/ai/tools.py' },
] as const;

const featureDeepDives = [
  {
    title: 'Canvas and Workflow Authoring',
    icon: 'node',
    intro: 'BioNodulo is built around an editable workflow graph rather than a form wizard. The UI keeps nodes, edges, groups, selections, and tabs visible while the backend validates the graph before execution.',
    points: [
      'Multi-tab workflow editing with browser-local persistence',
      'Node library, object metadata, searchable categories, defaults, and advanced fields',
      'Groups, selection tools, minimap, keyboard shortcuts, undo, redo, and canvas settings',
      'Structural validation through /api/workflow/validate before expensive runs',
    ],
    proof: ['web/src/App.tsx', 'web/src/components/canvas/LiteGraphCanvas.tsx', 'bionodulo/workflow/validation.py'],
  },
  {
    title: 'Bioinformatics Node Library',
    icon: 'cube',
    intro: 'The node registry covers practical analysis domains rather than a tiny demo set. The current codebase includes command nodes, visual-only nodes, output preview nodes, R helpers, and BioPython utilities.',
    points: [
      'Alignment, SAM/BAM processing, variant calling, assembly, annotation, QC, trimming, RNA-Seq, ChIP-Seq, metagenomics, phylogeny, single-cell, R, and BioPython nodes',
      'Typed ports and generated forms for node parameters',
      'Hidden and visual-only node metadata for UX-specific behavior',
      'External tool metadata feeds dependency diagnostics and environment planning',
    ],
    proof: ['bionodulo/nodes/builtin', 'bionodulo/nodes/registry.py', 'web/src/components/panels/NodeLibraryPanel.tsx'],
  },
  {
    title: 'Templates and Local-First Startup',
    icon: 'template',
    intro: 'Templates are available even when the collaboration server path is unreachable. The frontend falls back to bundled local template definitions and can load them directly into the canvas.',
    points: [
      '13 built-in templates spanning QC, RNA-Seq, DESeq2, WGS, variant calling, assembly, metagenomics, ChIP-Seq, phylogenetics, single-cell, R visualization, and BioPython',
      'Search and category filters in the templates panel',
      'Getting Started flow lets users choose local/offline mode or collaboration',
      'Template workflows are remapped to fresh node IDs before insertion',
    ],
    proof: ['templates/*.json', 'web/src/localTemplates.ts', 'web/src/components/panels/TemplatesPanel.tsx'],
  },
  {
    title: 'Execution, Queue, Logs, and Previews',
    icon: 'play',
    intro: 'Runs are submitted through the backend queue, streamed back over WebSocket events, and summarized in the bottom console with logs, queue, history, and previews.',
    points: [
      'Run submission through /api/runs with optional cache bypass and workflow environment selection',
      'Queue and history are restored on startup from /api/queue and /api/history',
      'Real-time node lifecycle events, cache hits, skips, errors, and completion logs',
      'Image preview lightbox and artifact links for workflow outputs',
    ],
    proof: ['bionodulo/execution', 'bionodulo/api/websocket.py', 'web/src/components/layout/BottomConsole.tsx'],
  },
  {
    title: 'Dependency and Environment Management',
    icon: 'grid',
    intro: 'The app audits host prerequisites, resolves workflow dependencies, and manages workflow-scoped environments instead of asking users to fix every missing command manually.',
    points: [
      'Host diagnostics and Pixi prerequisite checks',
      'Dependency resolver report and install plan flow',
      'Create, list, rename, duplicate, inspect, and delete workflow environments',
      'Package removal and ready/status indicators for environments',
    ],
    proof: ['bionodulo/manager', 'bionodulo/environments', 'web/src/components/panels/EnvironmentPanel.tsx'],
  },
  {
    title: 'Collaboration System',
    icon: 'users',
    intro: 'Collaboration is intentionally optional. When enabled, the app uses Yjs document updates, IndexedDB persistence, awareness state, JWT auth, permissions, comments, versions, templates, and audits.',
    points: [
      'Native Yjs sync and awareness messages over /ws/collab/{workflow_id}',
      'IndexedDB-backed offline document persistence on the frontend',
      'Sharing roles, public room status, comments, replies, resolve/delete, and active-user list',
      'Version save/list/diff/restore/delete plus audit query and CSV export',
    ],
    proof: ['web/src/collab', 'bionodulo/collab', 'bionodulo/api/collab_routes.py'],
  },
  {
    title: 'HPC and Portable Workflow Formats',
    icon: 'server',
    intro: 'BioNodulo keeps the local canvas as the authoring surface while supporting cluster-oriented execution and export paths for existing workflow ecosystems.',
    points: [
      'SLURM, PBS/Torque, and SGE backend classes',
      'Scheduler resource fields for partition, account, walltime, CPUs, memory, modules, containers, and extra args',
      'Workflow export to BioNodulo JSON, Snakemake, Nextflow, CWL, and Galaxy',
      'Import paths for BioNodulo JSON, Snakemake, Nextflow, CWL, and Galaxy',
    ],
    proof: ['bionodulo/hpc', 'bionodulo/workflow/export.py', 'bionodulo/converter'],
  },
  {
    title: 'AI Assistant',
    icon: 'code',
    intro: 'The assistant is wired into the workflow model rather than being a disconnected chat box. It can inspect the graph, use registry metadata, validate edits, and propose changes back to the UI.',
    points: [
      'Tools for current workflow, available nodes, node info, validation, dependencies, environments, templates, settings, system stats, run history, and collaboration status',
      'Mutating tools for adding, updating, removing, and connecting nodes, loading templates, and changing workflow name or description',
      'Persistent chat sessions, file attachments up to 5MB, pasted selected nodes, images, text files, and best-effort PDF extraction',
      'Provider settings for OpenAI, Anthropic, and custom API-compatible endpoints',
    ],
    proof: ['bionodulo/ai/tools.py', 'bionodulo/ai/assistant.py', 'web/src/components/modals/AIWorkflowModal.tsx'],
  },
] as const;

const nodeCategoryRows = [
  ['Alignment', '12'],
  ['Variant', '9'],
  ['Input', '7'],
  ['Metagenomics', '7'],
  ['RNA-Seq', '7'],
  ['Assembly', '6'],
  ['BioPython', '6'],
  ['SAMtools', '6'],
  ['Phylogeny', '5'],
  ['ChIP-Seq', '4'],
  ['R / Plotting', '4'],
  ['Utilities', '4+'],
] as const;

const workflowTemplateRows = [
  'FASTQ QC Pipeline',
  'RNA-Seq Pipeline',
  'DESeq2 Differential Expression',
  'WGS Variant Pipeline',
  'Variant Calling Pipeline',
  'Genome Assembly',
  'Metagenomics Profiling',
  'ChIP-Seq Pipeline',
  'Phylogenetics Pipeline',
  'Single Cell RNA-Seq',
  'R Visualization Pipeline',
  'Biopython Analysis Pipeline',
  'Differential Expression',
] as const;

function PageLayout({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const targets = Array.from(document.querySelectorAll<HTMLElement>('.reveal, .pop-in'));
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add('is-visible');
      });
    }, { threshold: 0.14 });
    targets.forEach(target => observer.observe(target));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <Header />
      <main className="page-main">{children}</main>
      <Footer />
    </>
  );
}

function PageHero({ label, title, text }: { label: string; title: string; text: string }) {
  return (
    <section className="page-hero reveal">
      <span className="beta">{label}</span>
      <h1>{title}</h1>
      <p>{text}</p>
    </section>
  );
}

function FeaturesPage() {
  return (
    <PageLayout>
      <PageHero
        label="Features"
        title="The app surface, mapped from the code."
        text="This page was rebuilt from a code audit of the frontend, backend, collaboration layer, node registry, execution system, converters, HPC backends, templates, and AI assistant tools."
      />

      <section className="feature-audit-strip reveal" aria-label="Feature audit summary">
        {featureAuditStats.map(stat => (
          <div className="feature-audit-stat pop-in" key={stat.label}>
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
            <p>{stat.detail}</p>
          </div>
        ))}
      </section>

      <section className="feature-overview reveal">
        <div>
          <span className="section-kicker">Audit Summary</span>
          <h2>BioNodulo is more than a canvas.</h2>
        </div>
        <p>
          The current implementation spans workflow authoring, local execution, dependency management,
          environment lifecycle, import and export, optional real-time collaboration, cluster submission,
          and a tool-backed assistant. The detailed sections below reflect what is already wired into
          the codebase today.
        </p>
      </section>

      <section className="detail-grid feature-primer-grid">
        {detailedFeatures.map(feature => (
          <article className="detail-card feature-primer-card pop-in" key={feature.title}>
            <div className="icon-shell"><Icon name={feature.icon} /></div>
            <h2>{feature.title}</h2>
            <p>{feature.text}</p>
            <ul>{feature.bullets.map(bullet => <li key={bullet}><Icon name="check" /> {bullet}</li>)}</ul>
          </article>
        ))}
      </section>

      <section className="feature-deep-list">
        {featureDeepDives.map((feature, index) => (
          <article className="feature-deep-card reveal" key={feature.title}>
            <div className="feature-deep-index">0{index + 1}</div>
            <div className="feature-deep-main">
              <div className="feature-deep-heading">
                <div className="icon-shell"><Icon name={feature.icon} /></div>
                <div>
                  <h2>{feature.title}</h2>
                  <p>{feature.intro}</p>
                </div>
              </div>
              <ul className="feature-check-list">
                {feature.points.map(point => <li key={point}><Icon name="check" /> {point}</li>)}
              </ul>
            </div>
            <aside className="feature-proof">
              <strong>Code audited</strong>
              {feature.proof.map(item => <code key={item}>{item}</code>)}
            </aside>
          </article>
        ))}
      </section>

      <section className="feature-inventory reveal">
        <div className="feature-inventory-panel">
          <span className="section-kicker">Node Inventory</span>
          <h2>Coverage by category</h2>
          <div className="category-bars">
            {nodeCategoryRows.map(([label, count]) => (
              <div className="category-row" key={label}>
                <span>{label}</span>
                <div><i style={{ width: `${Math.max(18, Number.parseInt(count, 10) * 7)}%` }} /></div>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="feature-inventory-panel">
          <span className="section-kicker">Template Library</span>
          <h2>Built-in starting points</h2>
          <div className="template-list">
            {workflowTemplateRows.map(template => (
              <span key={template}><Icon name="check" /> {template}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="feature-workflow-band reveal">
        <div>
          <span className="section-kicker">Workflow Lifecycle</span>
          <h2>From local drafting to shared review.</h2>
          <p>
            BioNodulo starts in local mode, lets users build and validate the graph, resolves host
            requirements, runs jobs locally or through configured HPC backends, and can then export
            or share the workflow when the project needs review.
          </p>
        </div>
        <div className="workflow-steps">
          {['Design', 'Validate', 'Resolve', 'Run', 'Preview', 'Export', 'Share'].map(step => (
            <span key={step}>{step}</span>
          ))}
        </div>
      </section>
    </PageLayout>
  );
}

function DownloadPage() {
  return (
    <PageLayout>
      <PageHero label="Download" title="Run BioNodulo your way." text="Start locally from GitHub, use a future notebook launch path, or choose hosted cloud when that option becomes available." />
      <section className="option-grid">
        <article className="option-card pop-in">
          <Icon name="github" />
          <h2>GitHub</h2>
          <p>Clone the open-source repository, inspect the code, and run BioNodulo locally.</p>
          <a className="button primary" href="https://github.com/Classacre/BioNodulo" target="_blank" rel="noreferrer">Open GitHub <Icon name="arrow" /></a>
        </article>
        <article className="option-card pop-in">
          <Icon name="code" />
          <h2>Google Colab</h2>
          <p>A notebook launch option is planned. This placeholder will point to the Colab notebook once it exists.</p>
          <a className="button secondary" href="#" aria-disabled="true">Coming Soon</a>
        </article>
        <article className="option-card pop-in">
          <Icon name="server" />
          <h2>Cloud Hosting</h2>
          <p>Future hosted services can bundle licensing with RDP or VPS infrastructure for teams that want managed access.</p>
          <a className="button primary" href="/pricing">View Pricing <Icon name="arrow" /></a>
        </article>
      </section>
    </PageLayout>
  );
}

function PricingPage() {
  const plans = [
    { name: 'Free', price: 'Free', text: 'Open-source and free for academic and non-commercial research purposes.', icon: 'gift' as const },
    { name: 'Publishing', price: 'TBD', text: 'Required for commercial use or publishing results produced with BioNodulo.', icon: 'license' as const },
    { name: 'Institutional', price: 'TBD', text: 'For institutions that need licensing, deployment help, and future hosted options.', icon: 'building' as const },
  ];

  return (
    <PageLayout>
      <PageHero label="Pricing" title="Licensing built around research first." text="BioNodulo is currently in open beta. Publishing and institutional pricing will be finalized as the platform matures." />
      <section className="pricing-grid">
        {plans.map(plan => (
          <article className="pricing-card pop-in" key={plan.name}>
            <Icon name={plan.icon} />
            <h2>{plan.name}</h2>
            <strong>{plan.price}</strong>
            <p>{plan.text}</p>
            <a className="button secondary" href={plan.name === 'Free' ? 'https://github.com/Classacre/BioNodulo' : '/contact'}>{plan.name === 'Free' ? 'Get Started' : 'Contact Us'}</a>
          </article>
        ))}
      </section>
    </PageLayout>
  );
}

function ContactPage() {
  return (
    <PageLayout>
      <PageHero label="Contact" title="Talk to us about BioNodulo." text="For publishing licenses, institutional plans, cloud hosting, or open beta feedback, send a note or use one of the community links." />
      <section className="contact-page-grid">
        <form className="contact-form pop-in">
          <label>Name<input type="text" name="name" placeholder="Your name" /></label>
          <label>Email<input type="email" name="email" placeholder="you@example.com" /></label>
          <label>Topic<select name="topic" defaultValue="licensing"><option value="licensing">Licensing</option><option value="institution">Institutional pricing</option><option value="hosting">Cloud hosting</option><option value="feedback">Open beta feedback</option></select></label>
          <label>Message<textarea name="message" placeholder="How can we help?" rows={6} /></label>
          <a className="button primary" href="mailto:nieuwenhuyzemikamartin@gmail.com">Email Message <Icon name="arrow" /></a>
        </form>
        <div className="contact-links pop-in">
          <a href="mailto:nieuwenhuyzemikamartin@gmail.com"><Icon name="mail" /> nieuwenhuyzemikamartin@gmail.com</a>
          <a href="https://www.linkedin.com/in/mika-nieuwenhuyzen/" target="_blank" rel="noreferrer"><Icon name="linkedin" /> LinkedIn</a>
          <a href="https://discord.gg/baNKVhZq6k" target="_blank" rel="noreferrer"><Icon name="discord" /> Discord</a>
          <a href="https://github.com/Classacre/BioNodulo" target="_blank" rel="noreferrer"><Icon name="github" /> GitHub Project</a>
        </div>
      </section>
    </PageLayout>
  );
}

function DemoPage() {
  return (
    <div className="demo-page">
      <Header />
      <main className="demo-shell">
        <div className="demo-copy">
          <span className="beta">Demo page coming next</span>
          <h1>Interactive BioNodulo demo</h1>
          <p>
            This page is reserved for the browser-based demo. It will eventually let visitors explore
            templates, inspect nodes, and run a guided workflow without installing BioNodulo.
          </p>
          <div className="hero-actions">
            <a className="button primary" href="/">Back to Site</a>
            <a className="button secondary" href="https://github.com/Classacre/BioNodulo" target="_blank" rel="noreferrer"><Icon name="github" /> GitHub</a>
          </div>
        </div>
        <ProductMockup />
      </main>
    </div>
  );
}

function App() {
  let page: React.ReactNode;

  switch (window.location.pathname) {
    case '/demo':
      page = <DemoPage />;
      break;
    case '/features':
      page = <FeaturesPage />;
      break;
    case '/download':
      page = <DownloadPage />;
      break;
    case '/pricing':
      page = <PricingPage />;
      break;
    case '/contact':
      page = <ContactPage />;
      break;
    default:
      page = <HomePage />;
  }

  return (
    <>
      <NoiseGradientBackground />
      {page}
    </>
  );
}

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('BioNodulo website root element is missing.');
}

const root =
  ((rootElement as HTMLElement & { __bionoduloRoot?: Root }).__bionoduloRoot ??=
    createRoot(rootElement));

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
