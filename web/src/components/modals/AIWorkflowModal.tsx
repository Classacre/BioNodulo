import { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import type { Workflow } from '../../types';
import { apiPost, ApiError } from '../../api/client';
import { renderMarkdownToHtml } from '../../utils/markdown';

interface AIWorkflowModalProps {
  workflow: Workflow;
  onClose: () => void;
  onApplyWorkflow: (wf: Workflow) => void;
}

interface ChatStep {
  type: 'thinking' | 'tool_call' | 'tool_result' | 'propose_changes' | 'reply';
  content: string;
  name?: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
  workflow?: Workflow;
  description?: string;
}

interface ChatTurn {
  role: 'user' | 'assistant';
  content?: string;
  steps?: ChatStep[];
  model?: string;
  files?: AttachedFile[];
}

interface AttachedFile {
  name: string;
  mime_type: string;
  content: string; // base64
}

interface ChatSession {
  id: string;
  name: string;
  turns: ChatTurn[];
  createdAt: number;
}

const STORAGE_KEY = 'bionodulo-ai-sessions';
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

const QUICK_PROMPTS: { id: string; labelKey: string; promptKey: string }[] = [
  { id: 'summary', labelKey: 'aiWorkflow.quickPrompts.summary.label', promptKey: 'aiWorkflow.quickPrompts.summary.prompt' },
  { id: 'failure', labelKey: 'aiWorkflow.quickPrompts.failure.label', promptKey: 'aiWorkflow.quickPrompts.failure.prompt' },
  { id: 'missingQc', labelKey: 'aiWorkflow.quickPrompts.missingQc.label', promptKey: 'aiWorkflow.quickPrompts.missingQc.prompt' },
  { id: 'nextStep', labelKey: 'aiWorkflow.quickPrompts.nextStep.label', promptKey: 'aiWorkflow.quickPrompts.nextStep.prompt' },
];

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return [];
}

function saveSessions(sessions: ChatSession[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch { /* ignore */ }
}

function makeId() {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function createSession(name: string, greeting: string): ChatSession {
  return {
    id: makeId(),
    name,
    turns: [
      {
        role: 'assistant',
        content: greeting,
      },
    ],
    createdAt: Date.now(),
  };
}

export default function AIWorkflowModal({ workflow, onClose, onApplyWorkflow }: AIWorkflowModalProps) {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const saved = loadSessions();
    return saved.length > 0 ? saved : [createSession(t('aiWorkflow.defaultSessionName'), t('aiWorkflow.greeting'))];
  });
  const [activeSessionId, setActiveSessionId] = useState<string>(sessions[0]?.id || '');
  const [showMenu, setShowMenu] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  // AbortController for the in-flight chat fetch — lets the user Stop a slow
  // tool-using turn instead of being forced to wait for it to finish.
  const inFlightRef = useRef<AbortController | null>(null);

  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0];
  const turns = activeSession?.turns || [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, sending]);

  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  // Close menu on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    }
    if (showMenu) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showMenu]);

  const createNewSession = useCallback(() => {
    const s = createSession(t('aiWorkflow.defaultSessionName'), t('aiWorkflow.greeting'));
    setSessions(prev => [s, ...prev]);
    setActiveSessionId(s.id);
    setShowMenu(false);
  }, [t]);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
    setShowMenu(false);
  }, []);

  const deleteSession = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id);
      if (next.length === 0) next.push(createSession(t('aiWorkflow.defaultSessionName'), t('aiWorkflow.greeting')));
      return next;
    });
    setActiveSessionId(prev => {
      if (prev === id) {
        const remaining = sessions.filter(s => s.id !== id);
        return remaining[0]?.id || createSession(t('aiWorkflow.defaultSessionName'), t('aiWorkflow.greeting')).id;
      }
      return prev;
    });
  }, [sessions, t]);

  const startRename = useCallback((s: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingId(s.id);
    setRenameValue(s.name);
  }, []);

  const commitRename = useCallback(() => {
    if (!renamingId || !renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    setSessions(prev =>
      prev.map(s => (s.id === renamingId ? { ...s, name: renameValue.trim() } : s))
    );
    setRenamingId(null);
  }, [renamingId, renameValue]);

  const readFileAsAttachment = useCallback(async (file: File): Promise<AttachedFile | null> => {
    if (file.size > MAX_FILE_SIZE) return null;
    const content = await new Promise<string>(resolve => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.readAsDataURL(file);
    });
    return {
      name: file.name,
      mime_type: file.type || 'application/octet-stream',
      content,
    };
  }, []);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const newAttachments: AttachedFile[] = [];
    for (const file of Array.from(files)) {
      const att = await readFileAsAttachment(file);
      if (att) newAttachments.push(att);
    }
    setAttachments(prev => [...prev, ...newAttachments]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [readFileAsAttachment]);

  const handlePaste = useCallback(async (e: React.ClipboardEvent<HTMLInputElement>) => {
    const items = e.clipboardData.items;
    const text = e.clipboardData.getData('text');

    // Check for pasted canvas nodes (bionodulo_clipboard:...)
    if (text && text.startsWith('bionodulo_clipboard:')) {
      e.preventDefault();
      try {
        const payload = JSON.parse(text.slice('bionodulo_clipboard:'.length));
        const nodeCount = payload.nodes?.length || 0;
        const edgeCount = payload.edges?.length || 0;
        const nodeNames = payload.nodes?.map((n: any) => n.type || n.id).join(', ') || '';
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const file = new File([blob], `selected_nodes_${nodeCount}.json`, { type: 'application/json' });
        const att = await readFileAsAttachment(file);
        if (att) {
          setAttachments(prev => [...prev, att]);
          if (!input.trim()) {
            const nodeLabel = t('aiWorkflow.input.pastedNodes.nodeLabel', { count: nodeCount });
            const edgeSuffix = edgeCount > 0
              ? t('aiWorkflow.input.pastedNodes.edgeSuffix', {
                  edgeLabel: t('aiWorkflow.input.pastedNodes.edgeLabel', { count: edgeCount }),
                })
              : '';
            setInput(t('aiWorkflow.input.pastedNodes.prompt', { nodeLabel, edgeSuffix, nodeNames }));
          }
        }
      } catch { /* ignore malformed clipboard */ }
      return;
    }

    // Check for pasted image files
    if (items) {
      const imageFiles: File[] = [];
      for (const item of Array.from(items)) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
          const file = item.getAsFile();
          if (file) imageFiles.push(file);
        }
      }
      if (imageFiles.length > 0) {
        e.preventDefault();
        const newAttachments: AttachedFile[] = [];
        for (const file of imageFiles) {
          const att = await readFileAsAttachment(file);
          if (att) newAttachments.push(att);
        }
        setAttachments(prev => [...prev, ...newAttachments]);
      }
    }
  }, [readFileAsAttachment, input, t]);

  const removeAttachment = useCallback((index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  }, []);

  const sendChat = useCallback(async (
    userMsg: string,
    currentAttachments: AttachedFile[],
    historyOverride?: ChatTurn[],
  ) => {
    const historyTurns = historyOverride ?? turns;
    setSending(true);
    const abortController = new AbortController();
    inFlightRef.current = abortController;

    try {
      const history = historyTurns.map(t => ({
        role: t.role,
        content: t.content || t.steps?.map(s => s.content).join('\n') || '',
      }));

      const respondLocally = () => setSessions(prev =>
        prev.map(s =>
          s.id === activeSessionId
            ? { ...s, turns: [...s.turns, { role: 'assistant', content: getLocalResponse(userMsg, t) }] }
            : s
        )
      );
      try {
        const data = await apiPost<{ steps?: ChatStep[]; model?: string }>('/ai/chat', {
          message: userMsg,
          workflow,
          workflow_id: workflow.id || null,
          history,
          files: currentAttachments,
        }, { signal: abortController.signal });
        const steps: ChatStep[] = (data.steps || []).map((s: ChatStep) => ({
          ...s,
          workflow: s.workflow
            ? sanitizeWorkflow(s.workflow as unknown as Record<string, unknown>, workflow, t('common.untitled'))
            : undefined,
        }));
        const assistantTurn: ChatTurn = {
          role: 'assistant',
          steps,
          model: data.model || undefined,
        };
        setSessions(prev =>
          prev.map(s =>
            s.id === activeSessionId
              ? { ...s, turns: [...s.turns, assistantTurn] }
              : s
          )
        );
      } catch (err) {
        // AbortError: user clicked Stop. Append a "stopped" note instead of
        // falling back to canned local responses (which would feel wrong).
        if (err instanceof DOMException && err.name === 'AbortError') {
          setSessions(prev =>
            prev.map(s =>
              s.id === activeSessionId
                ? { ...s, turns: [...s.turns, { role: 'assistant', content: t('aiWorkflow.generation.stopped') }] }
                : s
            )
          );
        } else if (err instanceof ApiError || err instanceof Error) {
          respondLocally();
        } else {
          throw err;
        }
      }
    } catch {
      setSessions(prev =>
        prev.map(s =>
          s.id === activeSessionId
            ? { ...s, turns: [...s.turns, { role: 'assistant', content: getLocalResponse(userMsg, t) }] }
            : s
        )
      );
    }
    inFlightRef.current = null;
    setSending(false);
  }, [activeSessionId, turns, workflow, t]);

  const send = useCallback(async () => {
    if ((!input.trim() && attachments.length === 0) || sending) return;
    const userMsg = input.trim();
    setInput('');
    const currentAttachments = attachments;
    setAttachments([]);

    const userTurn: ChatTurn = {
      role: 'user',
      content: userMsg,
      files: currentAttachments.length > 0 ? currentAttachments : undefined,
    };

    setSessions(prev =>
      prev.map(s =>
        s.id === activeSessionId ? { ...s, turns: [...s.turns, userTurn] } : s
      )
    );

    await sendChat(userMsg, currentAttachments);
  }, [input, attachments, sending, activeSessionId, sendChat]);

  const stop = useCallback(() => {
    inFlightRef.current?.abort();
  }, []);

  // Regenerate strips the last assistant turn, then re-sends the previous
  // user turn. Useful when the model picked a bad tool path or produced a
  // weak answer and the user wants another shot without retyping.
  const regenerate = useCallback(async () => {
    if (sending) return;
    const lastUserIdx = [...turns].reverse().findIndex(t => t.role === 'user');
    if (lastUserIdx < 0) return;
    const realIdx = turns.length - 1 - lastUserIdx;
    const lastUserTurn = turns[realIdx];
    const userMsg = lastUserTurn.content || '';
    const currentAttachments = lastUserTurn.files || [];
    // Keep everything up to AND including the last user turn; drop assistant
    // turns that came after it (there should be exactly one).
    const truncated = turns.slice(0, realIdx + 1);
    setSessions(prev =>
      prev.map(s => (s.id === activeSessionId ? { ...s, turns: truncated } : s))
    );
    await sendChat(userMsg, currentAttachments, turns.slice(0, realIdx));
  }, [sending, turns, activeSessionId, sendChat]);

  const insertQuickPrompt = useCallback((prompt: string) => {
    setInput(prompt);
  }, []);

  const handleApply = useCallback(
    (proposed: Workflow) => {
      onApplyWorkflow(proposed);
      setSessions(prev =>
        prev.map(s =>
          s.id === activeSessionId
            ? {
                ...s,
                turns: [
                  ...s.turns,
                  { role: 'assistant', content: t('aiWorkflow.steps.applySuccess') },
                ],
              }
            : s
        )
      );
    },
    [onApplyWorkflow, activeSessionId, t]
  );

  return (
    <div className="ai-drawer" onClick={e => e.stopPropagation()}>
      {/* Header */}
      <div className="ai-drawer-header">
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            className="btn btn-icon btn-sm"
            onClick={() => setShowMenu(!showMenu)}
            title={t('aiWorkflow.sessions.openTitle')}
          >
            <Icon name="menu" size={16} />
          </button>
          <Icon name="wand" size={16} /> {t('aiWorkflow.title')}
        </span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('common.close')}>
          <Icon name="close" size={14} />
        </button>
      </div>

      {/* Session Menu Dropdown */}
      {showMenu && (
        <div className="ai-session-menu" ref={menuRef}>
          <div className="ai-session-menu-header">
            <strong>{t('aiWorkflow.sessions.menuTitle')}</strong>
            <button className="btn btn-primary btn-sm" onClick={createNewSession}>
              <Icon name="plus" size={12} /> {t('aiWorkflow.sessions.newSession')}
            </button>
          </div>
          <div className="ai-session-list">
            {sessions.map(s => (
              <div
                key={s.id}
                className={`ai-session-item ${s.id === activeSessionId ? 'active' : ''}`}
                onClick={() => switchSession(s.id)}
              >
                {renamingId === s.id ? (
                  <input
                    className="text-input text-input-sm"
                    value={renameValue}
                    onChange={e => setRenameValue(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') commitRename();
                      if (e.key === 'Escape') setRenamingId(null);
                    }}
                    onBlur={commitRename}
                    autoFocus
                    onClick={e => e.stopPropagation()}
                  />
                ) : (
                  <>
                    <span className="ai-session-name">{s.name}</span>
                    <span className="ai-session-meta">{t('aiWorkflow.sessions.messageCount', { count: s.turns.length })}</span>
                  </>
                )}
                {renamingId !== s.id && (
                  <div className="ai-session-actions">
                    <button
                      className="btn btn-icon btn-xs"
                      title={t('common.rename')}
                      onClick={e => startRename(s, e)}
                    >
                      <Icon name="edit" size={10} />
                    </button>
                    <button
                      className="btn btn-icon btn-xs"
                      title={t('common.delete')}
                      onClick={e => deleteSession(s.id, e)}
                    >
                      <Icon name="trash" size={10} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Body */}
      <div className="ai-drawer-body">
        <div className="ai-chat-scroll">
          {turns.map((turn, i) => (
            <div key={i} className={`ai-turn ${turn.role}`}>
              {turn.role === 'user' ? (
                <div className="ai-msg user">
                  {turn.content}
                  {turn.files && turn.files.length > 0 && (
                    <div className="ai-file-chips">
                      {turn.files.map((f, fi) => (
                        <span key={fi} className="ai-file-chip">
                          <Icon name="file" size={10} /> {f.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="ai-msg assistant">
                  {turn.steps ? (
                    <div className="ai-steps">
                      {turn.steps.map((step, si) => (
                        <StepRenderer key={si} step={step} onApply={handleApply} />
                      ))}
                      <div className="ai-model-badge">{turn.model || t('aiWorkflow.modelUnknown')}</div>
                    </div>
                  ) : (
                    <div
                      className="ai-markdown"
                      dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(turn.content || '') }}
                    />
                  )}
                </div>
              )}
            </div>
          ))}
          {sending && (
            <div className="ai-turn assistant">
              <div className="ai-msg assistant">
                <div className="ai-thinking-inline">
                  <span className="ai-spinner" />
                  {t('aiWorkflow.generation.thinking')}
                  <button
                    className="btn btn-sm btn-ghost"
                    style={{ marginLeft: 12 }}
                    onClick={stop}
                    title={t('aiWorkflow.generation.stopTitle')}
                  >
                    <Icon name="close" size={10} /> {t('aiWorkflow.generation.stop')}
                  </button>
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Footer */}
      <div className="ai-drawer-footer">
        {/* Quick prompt chips: only show when the conversation is empty (one
            primer assistant turn) and we're not mid-send. They let the user
            kick off a useful tool-using turn with one click. */}
        {turns.length <= 1 && !sending && (
          <div className="ai-quick-prompts">
            {QUICK_PROMPTS.map(qp => (
              <button
                key={qp.id}
                className="ai-quick-prompt"
                onClick={() => insertQuickPrompt(t(qp.promptKey))}
                title={t(qp.promptKey)}
              >
                {t(qp.labelKey)}
              </button>
            ))}
          </div>
        )}
        {/* Regenerate is offered after any assistant turn so the user can
            quickly retry without retyping the question. */}
        {!sending && turns.length > 1 && turns[turns.length - 1].role === 'assistant' && (
          <div className="ai-quick-prompts">
            <button className="ai-quick-prompt" onClick={regenerate} title={t('aiWorkflow.generation.regenerateTitle')}>
              ↻ {t('aiWorkflow.generation.regenerate')}
            </button>
          </div>
        )}
        {attachments.length > 0 && (
          <div className="ai-attachments-row">
            {attachments.map((f, i) => (
              <span key={i} className="ai-attachment-chip">
                <Icon name="file" size={10} /> {f.name}
                <button className="ai-attachment-remove" onClick={() => removeAttachment(i)}>
                  <Icon name="close" size={8} />
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="ai-input-row">
          <button
            className="btn btn-icon btn-sm"
            onClick={() => fileInputRef.current?.click()}
            title={t('aiWorkflow.input.attachFileTitle')}
          >
            <Icon name="paperclip" size={14} />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            style={{ display: 'none' }}
            multiple
            onChange={handleFileSelect}
          />
          <input
            type="text"
            className="text-input"
            style={{ flex: 1 }}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send()}
            onPaste={handlePaste}
            placeholder={t('aiWorkflow.input.placeholder')}
            disabled={sending}
          />
          {sending ? (
            <button className="btn btn-secondary" onClick={stop} title={t('aiWorkflow.generation.stopTitle')}>
              {t('aiWorkflow.generation.stop')}
            </button>
          ) : (
            <button className="btn btn-primary" onClick={send}>
              {t('aiWorkflow.input.send')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function StepRenderer({ step, onApply }: { step: ChatStep; onApply: (wf: Workflow) => void }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  switch (step.type) {
    case 'thinking':
      return (
        <div className="ai-step-thinking">
          <button className="ai-step-toggle" onClick={() => setExpanded(!expanded)}>
            <Icon name="lightbulb" size={12} />
            {expanded ? t('aiWorkflow.steps.hideReasoning') : t('aiWorkflow.steps.showReasoning')}
          </button>
          {expanded && <pre className="ai-step-pre">{step.content}</pre>}
        </div>
      );

    case 'tool_call':
      return (
        <div className="ai-step-tool-call">
          <div className="ai-step-header">
            <Icon name="terminal" size={12} />
            <span className="ai-step-name">{step.name}</span>
          </div>
          <pre className="ai-step-pre">{JSON.stringify(step.arguments, null, 2)}</pre>
        </div>
      );

    case 'tool_result':
      return (
        <div className="ai-step-tool-result">
          <div className="ai-step-header">
            <Icon name="check" size={12} />
            <span className="ai-step-name">{t('aiWorkflow.steps.toolResult', { name: step.name })}</span>
          </div>
          <pre className="ai-step-pre">{JSON.stringify(step.result, null, 2)}</pre>
        </div>
      );

    case 'propose_changes':
      return (
        <div className="ai-step-propose">
          <div className="ai-step-propose-header">
            <Icon name="edit" size={14} />
            <strong>{t('aiWorkflow.steps.proposedChanges')}</strong>
          </div>
          <p className="ai-step-propose-desc">{step.description || t('aiWorkflow.steps.proposalFallbackDescription')}</p>
          {step.workflow && (
            <div className="ai-step-propose-actions">
              <button className="btn btn-primary btn-sm" onClick={() => onApply(step.workflow!)}>
                {t('aiWorkflow.steps.applyChanges')}
              </button>
              <button
                className="btn btn-sm"
                onClick={async () => {
                  const payload = JSON.stringify({
                    nodes: step.workflow?.nodes || [],
                    edges: step.workflow?.edges || [],
                  });
                  const text = `bionodulo_clipboard:${payload}`;
                  try {
                    await navigator.clipboard.writeText(text);
                    setExpanded(true);
                  } catch { /* ignore */ }
                }}
              >
                <Icon name="copy" size={10} /> {t('aiWorkflow.steps.copyToCanvas')}
              </button>
              <button className="btn btn-sm" onClick={() => setExpanded(true)}>
                {t('aiWorkflow.steps.previewJson')}
              </button>
            </div>
          )}
          {expanded && step.workflow && (
            <pre className="ai-step-pre" style={{ maxHeight: 300, overflow: 'auto' }}>
              {JSON.stringify(step.workflow, null, 2)}
            </pre>
          )}
        </div>
      );

    case 'reply':
    default:
      return (
        <div
          className="ai-step-reply ai-markdown"
          dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(step.content) }}
        />
      );
  }
}

function stringValueOrFallback(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function sanitizeWorkflow(raw: Record<string, unknown>, fallback: Workflow | undefined, fallbackName: string): Workflow {
  return {
    id: typeof raw.id === 'string' ? raw.id : fallback?.id,
    version: stringValueOrFallback(raw.version, fallback?.version || '2.0'),
    app: stringValueOrFallback(raw.app, fallback?.app || 'bionodulo'),
    name: stringValueOrFallback(raw.name, fallback?.name || fallbackName),
    description: stringValueOrFallback(raw.description, fallback?.description || ''),
    nodes: Array.isArray(raw.nodes) ? raw.nodes : [],
    edges: Array.isArray(raw.edges) ? raw.edges : [],
    groups: Array.isArray(raw.groups) ? raw.groups : [],
    outputs: (raw.outputs as Record<string, string>) || {},
    environment: (raw.environment as Record<string, unknown>) || undefined,
    dependencies: (raw.dependencies as Record<string, string>) || undefined,
  } as Workflow;
}

function getLocalResponse(msg: string, t: ReturnType<typeof useTranslation>['t']): string {
  const lower = msg.toLowerCase();
  if (lower.includes('rna') || lower.includes('transcript')) {
    return t('aiWorkflow.localResponses.rna');
  }
  if (lower.includes('variant') || lower.includes('snp') || lower.includes('vcf')) {
    return t('aiWorkflow.localResponses.variant');
  }
  if (lower.includes('assembly') || lower.includes('spades') || lower.includes('megahit')) {
    return t('aiWorkflow.localResponses.assembly');
  }
  if (lower.includes('meta') || lower.includes('kraken') || lower.includes('humann')) {
    return t('aiWorkflow.localResponses.metagenomics');
  }
  if (lower.includes('chip') || lower.includes('peak')) {
    return t('aiWorkflow.localResponses.chipSeq');
  }
  if (lower.includes('qc') || lower.includes('quality') || lower.includes('fastqc')) {
    return t('aiWorkflow.localResponses.qc');
  }
  if (lower.includes('phylo') || lower.includes('tree')) {
    return t('aiWorkflow.localResponses.phylogenetics');
  }
  if (lower.includes('single cell') || lower.includes('scRNA') || lower.includes('cellranger')) {
    return t('aiWorkflow.localResponses.singleCell');
  }
  if (lower.includes('plot') || lower.includes('r ') || lower.includes('ggplot')) {
    return t('aiWorkflow.localResponses.plotting');
  }
  return t('aiWorkflow.localResponses.default');
}
