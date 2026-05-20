import React from 'react';
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

const stats = [
  { value: '94', label: 'Bioinformatics Nodes', detail: 'Registered node types in the app', icon: 'cube' },
  { value: '13', label: 'Workflow Templates', detail: 'Built-in analysis starting points', icon: 'template' },
  { value: '19', label: 'Node Categories', detail: 'QC, RNA-seq, variant calling, and more', icon: 'grid' },
  { value: '3', label: 'HPC Schedulers', detail: 'SLURM, PBS/Torque, and SGE', icon: 'server' },
] as const;

const features = [
  {
    title: 'Visual Workflow Builder',
    text: 'Drag, drop, connect, and inspect bioinformatics workflows as a node graph instead of a wall of scripts.',
    icon: 'node',
  },
  {
    title: 'Bioinformatics Node Library',
    text: '94 registered nodes across QC, alignment, RNA-seq, assembly, variant calling, metagenomics, R, BioPython, and more.',
    icon: 'cube',
  },
  {
    title: 'Local Execution by Default',
    text: 'Run on your own machine first, with local templates and local workflow state available without collaboration services.',
    icon: 'play',
  },
  {
    title: 'Optional Collaboration',
    text: 'Invite collaborators, share workflows, comment, inspect versions, and keep local mode as the default when working alone.',
    icon: 'users',
  },
  {
    title: 'HPC Ready',
    text: 'Configure SLURM, PBS/Torque, or SGE for research groups that need cluster execution.',
    icon: 'server',
  },
  {
    title: 'AI Workflow Assistant',
    text: 'Use the built-in assistant to inspect workflows, add nodes, validate edges, and draft changes for review.',
    icon: 'code',
  },
] as const;

const integrations = [
  'Python',
  'R',
  'Conda / Mamba',
  'SLURM',
  'PBS / Torque',
  'SGE',
  'Snakemake',
  'Nextflow',
  'CWL',
  'Galaxy',
];

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
      <span className="logo-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>BioNodulo</span>
    </a>
  );
}

function Header() {
  return (
    <header className="site-header">
      <Logo />
      <nav aria-label="Primary navigation">
        <a href="#features">Features</a>
        <a href="#templates">Templates</a>
        <a href="#integrations">Integrations</a>
        <a href="#licensing">Licensing</a>
        <a href="#faq">FAQ</a>
      </nav>
      <div className="header-actions">
        <a className="button secondary small" href="https://github.com/Classacre" target="_blank" rel="noreferrer">
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

function ProductMockup({ compact = false }: { compact?: boolean }) {
  const nodes = [
    { label: 'Input FASTQ', x: 15, y: 42, color: 'blue' },
    { label: 'FastQC', x: 41, y: 27, color: 'amber' },
    { label: 'Trim Reads', x: 62, y: 42, color: 'violet' },
    { label: 'STAR Align', x: 43, y: 63, color: 'cyan' },
    { label: 'DESeq2', x: 69, y: 64, color: 'green' },
  ];

  return (
    <div className={`product-mockup ${compact ? 'compact' : ''}`} aria-label="BioNodulo workflow editor preview">
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
          <a className="button secondary" href="https://github.com/Classacre" target="_blank" rel="noreferrer"><Icon name="github" /> GitHub</a>
        </div>
        <div className="trust-line">
          <span>Open Source</span>
          <span>Local-First</span>
          <span>Cross Platform</span>
          <span>Python Powered</span>
        </div>
      </div>
      <ProductMockup />
    </section>
  );
}

function Stats() {
  return (
    <section className="stats" aria-label="BioNodulo product statistics">
      {stats.map(stat => (
        <div className="stat" key={stat.label}>
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
  return (
    <section className="section" id="features">
      <div className="section-heading">
        <h2>Everything you need to do more research</h2>
        <p>BioNodulo keeps the workflow visible while still leaving room for serious local, HPC, and collaborative execution.</p>
      </div>
      <div className="feature-grid">
        {features.map(feature => (
          <article className="feature-card" key={feature.title}>
            <div className="icon-shell"><Icon name={feature.icon} /></div>
            <h3>{feature.title}</h3>
            <p>{feature.text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function LocalFirst() {
  return (
    <section className="split-section">
      <div className="system-card">
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
      <div className="split-copy">
        <span className="section-label">Local-first, private by design</span>
        <h2>Your data stays yours.</h2>
        <p>
          BioNodulo runs locally by default. Your data never leaves your machine unless you choose to share it.
          Enable collaboration when you are ready.
        </p>
        <div className="pill-grid">
          <span><Icon name="play" /> Runs Offline</span>
          <span><Icon name="lock" /> No Data Lock-in</span>
          <span><Icon name="eye" /> Full Transparency</span>
          <span><Icon name="check" /> Reproducible</span>
        </div>
      </div>
    </section>
  );
}

function Integrations() {
  return (
    <section className="section compact" id="integrations">
      <div className="section-heading">
        <h2>Works with the tools you already use</h2>
      </div>
      <div className="integration-grid">
        {integrations.map(item => <div className="integration" key={item}>{item}</div>)}
      </div>
    </section>
  );
}

function Licensing() {
  return (
    <section className="section" id="licensing">
      <div className="section-heading">
        <h2>Open Beta. Open Source. Open for Research.</h2>
        <p>Licensing is designed around research first, with institutional and hosted options coming as the platform matures.</p>
      </div>
      <div className="license-grid">
        {licensing.map(item => (
          <article className="license-card" key={item.title}>
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
    <section className="demo-callout" id="templates">
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
    <section className="section faq" id="faq">
      <div className="section-heading">
        <h2>Frequently Asked Questions</h2>
      </div>
      <div className="faq-grid">
        {faqs.map(item => (
          <details key={item.question}>
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
          <a href="https://github.com/Classacre" aria-label="GitHub" target="_blank" rel="noreferrer"><Icon name="github" /></a>
          <a href="https://discord.gg/baNKVhZq6k" aria-label="Discord" target="_blank" rel="noreferrer"><Icon name="discord" /></a>
          <a href="https://www.linkedin.com/in/mika-nieuwenhuyzen/" aria-label="LinkedIn" target="_blank" rel="noreferrer"><Icon name="linkedin" /></a>
          <a href="mailto:nieuwenhuyzemikamartin@gmail.com" aria-label="Email"><Icon name="mail" /></a>
        </div>
      </div>
      <div className="footer-links">
        <div><strong>Product</strong><a href="#features">Features</a><a href="#templates">Templates</a><a href="#integrations">Integrations</a><a href="/demo">Demo</a></div>
        <div><strong>Community</strong><a href="https://github.com/Classacre" target="_blank" rel="noreferrer">GitHub</a><a href="https://discord.gg/baNKVhZq6k" target="_blank" rel="noreferrer">Discord</a><a href="#faq">FAQ</a></div>
        <div><strong>Company</strong><a href="mailto:nieuwenhuyzemikamartin@gmail.com">Contact</a><a href="#licensing">Licensing</a><a href="https://www.linkedin.com/in/mika-nieuwenhuyzen/" target="_blank" rel="noreferrer">LinkedIn</a></div>
      </div>
      <div className="footer-bottom">
        <span>© 2026 BioNodulo</span>
        <span>Contact: nieuwenhuyzemikamartin@gmail.com</span>
      </div>
    </footer>
  );
}

function HomePage() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Stats />
        <Features />
        <LocalFirst />
        <Integrations />
        <Licensing />
        <DemoCallout />
        <FAQ />
      </main>
      <Footer />
    </>
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
            <a className="button secondary" href="https://github.com/Classacre" target="_blank" rel="noreferrer"><Icon name="github" /> GitHub</a>
          </div>
        </div>
        <ProductMockup />
      </main>
    </div>
  );
}

function App() {
  return window.location.pathname === '/demo' ? <DemoPage /> : <HomePage />;
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
