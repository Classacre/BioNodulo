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
    { role: 'assistant', content: 'Hello! I can help you build bioinformatics workflows. What kind of analysis are you working on?' },
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
        body: JSON.stringify({ message: userMsg, history: messages }),
      });
      if (r.ok) {
        const data = await r.json();
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply || 'I can help with that! Let me know if you need more details.' }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: getLocalResponse(userMsg) }]);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: getLocalResponse(userMsg) }]);
    }
    setSending(false);
  };

  return (
    <div className="ai-drawer" onClick={e => e.stopPropagation()}>
      <div className="ai-drawer-header">
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="wand" size={16} /> AI Workflow Assistant
        </span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title="Close">
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="ai-drawer-body">
        <div className="ai-chat-scroll">
          {messages.map((m, i) => (
            <div key={i} className={`ai-msg ${m.role}`} style={m.role === 'user' ? { alignSelf: 'flex-end' } : {}}>
              {m.content}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
      <div className="ai-drawer-footer">
        <div className="ai-input-row">
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
  );
}

function getLocalResponse(msg: string): string {
  const lower = msg.toLowerCase();
  if (lower.includes('rna') || lower.includes('transcript')) {
    return 'For RNA-Seq, I recommend: input_fastq → fastp (trim) → STAR or HISAT2 (align) → featureCounts (quantify). Add a Sample Sheet node for multi-sample runs. The RNA-Seq template has this wired up for you!';
  }
  if (lower.includes('variant') || lower.includes('snp') || lower.includes('vcf')) {
    return 'For variant calling: input_fastq → fastp → BWA-MEM → samtools sort/index → GATK HaplotypeCaller → bcftools filter. The Variant Calling template includes BAM QC with samtools flagstat too.';
  }
  if (lower.includes('assembly') || lower.includes('spades') || lower.includes('megahit')) {
    return 'For assembly: input_fastq → fastp → SPAdes (or MEGAHIT for metagenomes) → QUAST (quality assessment). If you have a reference, add it to QUAST for comparative metrics.';
  }
  if (lower.includes('meta') || lower.includes('kraken') || lower.includes('humann')) {
    return 'For metagenomics: input_fastq → Kraken2 (taxonomic classification) → Bracken (abundance estimation) → MetaPhlAn (profile) → HUMAnN (functional profiling). The Metagenomics template has the full pipeline.';
  }
  if (lower.includes('chip') || lower.includes('peak')) {
    return 'For ChIP-Seq: input_fastq → Bowtie2 → samtools sort → MACS2 CallPeak. Add a control BAM to the MACS2 node for proper peak calling.';
  }
  if (lower.includes('qc') || lower.includes('quality') || lower.includes('fastqc')) {
    return 'For QC: input_fastq → FastQC (per-sample reports) → MultiQC (aggregated report). This is the simplest pipeline and a great starting point!';
  }
  if (lower.includes('phylo') || lower.includes('tree')) {
    return 'For phylogenetics: input_fasta → MAFFT (alignment) → IQ-TREE (tree inference). You can also try FastTree for quick exploratory trees.';
  }
  if (lower.includes('single cell') || lower.includes('scRNA') || lower.includes('cellranger')) {
    return 'For single-cell: input_directory (FASTQs) + reference_transcriptome → Cell Ranger Count. The Single Cell template is pre-configured for 10x Genomics data.';
  }
  if (lower.includes('plot') || lower.includes('r ') || lower.includes('ggplot')) {
    return 'For plotting: use the R Plot node. Connect a DataFrame Builder node with your x/y columns, choose scatter/line/bar/boxplot, and set optional color/title parameters.';
  }
  return 'I can help you design bioinformatics workflows! Try asking about RNA-Seq, variant calling, assembly, metagenomics, ChIP-Seq, QC, phylogenetics, or single-cell analysis.';
}
