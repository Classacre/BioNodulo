import { useState, useRef, useEffect } from 'react';
import Icon from '../ui/Icon';

interface AIWorkflowModalProps {
  onClose: () => void;
}

interface ChatMsg {
  role: 'user' | 'assistant';
  content: string;
}

export default function AIWorkflowModal({ onClose }: AIWorkflowModalProps) {
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: 'assistant', content: 'Hello! I can help you build bioinformatics workflows. Describe what you want to achieve, and I will suggest nodes and connections. For example: "I want to do RNA-Seq analysis starting from FASTQ files" or "Build a variant calling pipeline for human WGS data".' },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async () => {
    if (!input.trim() || sending) return;
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setSending(true);

    try {
      const r = await fetch('/api/ai/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [...messages, { role: 'user', content: userMsg }] }),
      });
      if (r.ok) {
        const data = await r.json();
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply || 'I can help with that! Try using the RNA-Seq template or add individual nodes from the node palette.' }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: getLocalResponse(userMsg) }]);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: getLocalResponse(userMsg) }]);
    }
    setSending(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ width: 600, height: 500, display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Icon name="wand" size={16} /> AI Workflow Assistant</span>
          <button className="btn btn-icon btn-sm" onClick={onClose}><Icon name="close" size={14} /></button>
        </div>
        <div className="modal-body" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: 0 }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {messages.map((m, i) => (
              <div key={i} className={`ai-msg ${m.role}`} style={m.role === 'user' ? { alignSelf: 'flex-end' } : {}}>
                {m.content}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>
        <div className="modal-footer" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="ai-input-row" style={{ flex: 1, display: 'flex', gap: 8 }}>
            <input
              type="text"
              className="text-input"
              style={{ flex: 1 }}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              placeholder="Ask about workflows..."
              disabled={sending}
            />
            <button className="btn btn-primary" onClick={send} disabled={sending}>
              {sending ? '...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function getLocalResponse(msg: string): string {
  const lower = msg.toLowerCase();
  if (lower.includes('rna') || lower.includes('transcript')) {
    return 'For RNA-Seq analysis, I recommend this pipeline:\n1. Input FASTQ files → HISAT2 or STAR for alignment\n2. Aligned reads → featureCounts for quantification\n3. Run FastQC on raw reads and MultiQC for summary\n\nYou can also use Salmon or Kallisto for pseudo-alignment. Load the RNA-Seq template from the Templates panel for a complete setup!';
  }
  if (lower.includes('variant') || lower.includes('vcf') || lower.includes('snp')) {
    return 'For variant calling, try this approach:\n1. Input FASTQ → BWA-MEM for alignment\n2. Sort and index BAM with samtools\n3. Run GATK HaplotypeCaller or bcftools mpileup → VCF\n4. Filter variants with bcftools filter\n\nLoad the Variant Calling template for a complete pipeline!';
  }
  if (lower.includes('assemble') || lower.includes('genome')) {
    return 'For genome assembly:\n1. Input FASTQ reads → SPAdes (small genomes) or MEGAHIT (metagenomes)\n2. Evaluate with Quast\n3. Annotate with Prokka or Bakta\n\nFor long reads, consider Flye (Nanopore) or Canu (PacBio). Check the Assembly template!';
  }
  if (lower.includes('meta') || lower.includes('microbiome') || lower.includes('taxon')) {
    return 'For metagenomics:\n1. Input FASTQ → Kraken2 for taxonomic classification\n2. Bracken for abundance estimation\n3. MetaPhlAn as alternative classifier\n4. HUMAnN for functional profiling\n\nThe Metagenomics template has this all set up!';
  }
  if (lower.includes('chip') || lower.includes('peak')) {
    return 'For ChIP-Seq:\n1. Input FASTQ → Bowtie2 for alignment\n2. MACS2 for peak calling\n3. deepTools for coverage visualization\n\nLoad the ChIP-Seq template for the full pipeline.';
  }
  return 'I can help you build that! Try browsing the Templates panel for pre-built workflows, or use the Node Library to add individual tools. You can also ask me about specific tools or categories.';
}
