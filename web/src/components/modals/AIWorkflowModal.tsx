import { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import type { Workflow } from '../../types';
import { apiGet, ApiError } from '../../api/client';
import { streamAIChat, type AIChatStep } from '../../api/aiChat';
import { logError } from '../../state/logging';
import { renderMarkdownToHtml } from '../../utils/markdown';
import {
  AI_DRAWER_DEFAULT_WIDTH,
  clampDrawerWidth,
  filterSkills,
  type SkillSummary,
} from '../../utils/aiAssistant';

interface AIWorkflowModalProps {
  workflow: Workflow;
  onClose: () => void;
  onApplyWorkflow: (wf: Workflow) => void;
}

interface ChatStep extends Omit<AIChatStep, 'workflow'> {
  workflow?: Workflow;
}

interface ChatTurn {
  role: 'user' | 'assistant';
  content?: string;
  steps?: ChatStep[];
  model?: string;
  files?: AttachedFile[];
  /** Backend/network failure marker: renders the muted error bubble instead of
   *  markdown. `content` carries the raw error message. */
  isError?: boolean;
  streaming?: boolean;
  startedAt?: number;
  lastActivityAt?: number;
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
const DRAWER_WIDTH_KEY = 'bionodulo.ai.drawerWidth';
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
// The existing mobile media query collapses the drawer to full-width at this
// breakpoint; below it the saved/inline width must not apply.
const DRAWER_FULL_WIDTH_BREAKPOINT = 768;

const QUICK_PROMPTS: { id: string; labelKey: string; promptKey: string }[] = [
  { id: 'summary', labelKey: 'aiWorkflow.quickPrompts.summary.label', promptKey: 'aiWorkflow.quickPrompts.summary.prompt' },
  { id: 'failure', labelKey: 'aiWorkflow.quickPrompts.failure.label', promptKey: 'aiWorkflow.quickPrompts.failure.prompt' },
  { id: 'missingQc', labelKey: 'aiWorkflow.quickPrompts.missingQc.label', promptKey: 'aiWorkflow.quickPrompts.missingQc.prompt' },
  { id: 'nextStep', labelKey: 'aiWorkflow.quickPrompts.nextStep.label', promptKey: 'aiWorkflow.quickPrompts.nextStep.prompt' },
];

function loadSessions(interruptedLabel: string): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return (JSON.parse(raw) as ChatSession[]).map(session => ({
      ...session,
      turns: session.turns.map(turn => turn.streaming
        ? { ...turn, streaming: false, steps: [...(turn.steps || []), { type: 'status', content: interruptedLabel }] }
        : turn),
    }));
  } catch { /* ignore */ }
  return [];
}

function saveSessions(sessions: ChatSession[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch { /* ignore */ }
}

function loadDrawerWidth(): number {
  try {
    const raw = localStorage.getItem(DRAWER_WIDTH_KEY);
    if (raw) {
      const parsed = Number(raw);
      if (Number.isFinite(parsed)) return parsed;
    }
  } catch { /* ignore */ }
  return AI_DRAWER_DEFAULT_WIDTH;
}

function makeId() {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function appendChatStep(steps: ChatStep[], step: ChatStep): ChatStep[] {
  if (step.type === 'reply_delta') {
    const last = steps[steps.length - 1];
    if (last?.type === 'reply_delta' && (!step.id || !last.id || step.id === last.id)) {
      return [...steps.slice(0, -1), { ...last, content: last.content + step.content }];
    }
  }
  if (step.type === 'reply') {
    return [...steps.filter(previous => previous.type !== 'reply_delta' || (step.id && previous.id && previous.id !== step.id)), step];
  }
  if (step.type === 'commentary' && step.id) {
    return [...steps.filter(previous => previous.type !== 'reply_delta' || previous.id !== step.id), step];
  }
  return [...steps, step];
}

function toolResultState(step: ChatStep): 'completed' | 'error' | 'cancelled' {
  const inner = step.result?.result;
  if (step.result?.status === 'cancelled' ||
      (inner && typeof inner === 'object' && (inner as Record<string, unknown>).status === 'cancelled')) {
    return 'cancelled';
  }
  return step.status === 'error' ? 'error' : 'completed';
}

function displayToolName(name: string | undefined, fallback: string): string {
  const spaced = (name || fallback).replace(/[_-]+/g, ' ').trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
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

// Module-level skill cache: /ai/skills is fetched at most once per page
// lifetime (the skill list only changes when packs are imported). A failed
// fetch clears the in-flight promise so the next '/' keystroke retries.
let skillsCache: SkillSummary[] | null = null;
let skillsRequest: Promise<SkillSummary[]> | null = null;

function loadSkills(): Promise<SkillSummary[]> {
  if (skillsCache) return Promise.resolve(skillsCache);
  if (!skillsRequest) {
    skillsRequest = apiGet<{ skills?: SkillSummary[] }>('/ai/skills')
      .then(data => {
        skillsCache = Array.isArray(data?.skills) ? data.skills : [];
        return skillsCache;
      })
      .catch(err => {
        skillsRequest = null;
        throw err;
      });
  }
  return skillsRequest;
}

export default function AIWorkflowModal({ workflow, onClose, onApplyWorkflow }: AIWorkflowModalProps) {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const saved = loadSessions(t('aiWorkflow.generation.interrupted'));
    return saved.length > 0 ? saved : [createSession(t('aiWorkflow.defaultSessionName'), t('aiWorkflow.greeting'))];
  });
  const [activeSessionId, setActiveSessionId] = useState<string>(sessions[0]?.id || '');
  const [showMenu, setShowMenu] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  // Pop-out mode: same chat state, larger centered window with a session
  // sidebar. `false` is the classic right-hand drawer.
  const [isPoppedOut, setIsPoppedOut] = useState(false);
  // Resizable drawer width (drawer mode only; persisted).
  const [drawerWidth, setDrawerWidth] = useState(() =>
    clampDrawerWidth(loadDrawerWidth(), typeof window === 'undefined' ? 1024 : window.innerWidth)
  );
  const [isResizing, setIsResizing] = useState(false);
  const [viewportWidth, setViewportWidth] = useState(() =>
    typeof window === 'undefined' ? 1024 : window.innerWidth
  );
  // Slash-command skill autocomplete. skillQuery === null means the dropdown
  // is closed; otherwise it is the text after the leading '/'.
  const [availableSkills, setAvailableSkills] = useState<SkillSummary[]>(skillsCache || []);
  const [skillQuery, setSkillQuery] = useState<string | null>(null);
  const [skillIndex, setSkillIndex] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const resizeDragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  // AbortController for the in-flight chat fetch — lets the user Stop a slow
  // tool-using turn instead of being forced to wait for it to finish.
  const inFlightRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);
  const activeSessionIdRef = useRef(activeSessionId);

  useEffect(() => { activeSessionIdRef.current = activeSessionId; }, [activeSessionId]);
  useEffect(() => {
    if (!sending) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [sending]);
  useEffect(() => () => {
    requestIdRef.current++;
    inFlightRef.current?.abort();
  }, []);

  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0];
  const turns = activeSession?.turns || [];

  const skillMatches = skillQuery !== null ? filterSkills(skillQuery, availableSkills) : [];
  const skillDropdownVisible = skillQuery !== null && skillMatches.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, sending]);

  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  // Persist the drawer width (clamped value, so a tiny viewport never stores a
  // width that would be off-screen on a larger display).
  useEffect(() => {
    try {
      localStorage.setItem(DRAWER_WIDTH_KEY, String(drawerWidth));
    } catch { /* ignore */ }
  }, [drawerWidth]);

  // Track the viewport so the inline drawer width can be suppressed when the
  // CSS media query takes over (mobile full-width drawer).
  useEffect(() => {
    function handleResize() {
      setViewportWidth(window.innerWidth);
    }
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Esc leaves pop-out mode (back to the drawer). Skill-dropdown Escape and
  // session-rename Escape handle themselves first.
  useEffect(() => {
    if (!isPoppedOut) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key !== 'Escape') return;
      if (renamingId !== null || skillQuery !== null) return;
      setIsPoppedOut(false);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [isPoppedOut, renamingId, skillQuery]);

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

  // Keep the highlighted skill inside the visible match list.
  useEffect(() => {
    setSkillIndex(i => Math.min(i, Math.max(skillMatches.length - 1, 0)));
  }, [skillMatches.length]);

  const interruptCurrentTurn = useCallback(() => {
    inFlightRef.current?.abort();
    requestIdRef.current++;
    setSending(false);
    const sessionId = activeSessionIdRef.current;
    setSessions(prev => prev.map(session => session.id === sessionId ? {
      ...session,
      turns: session.turns.map(turn => turn.streaming ? {
        ...turn,
        streaming: false,
        steps: [...(turn.steps || []), { type: 'status', content: t('aiWorkflow.generation.stopped') } as ChatStep],
      } : turn),
    } : session));
  }, [t]);

  const createNewSession = useCallback(() => {
    if (inFlightRef.current) interruptCurrentTurn();
    const s = createSession(t('aiWorkflow.defaultSessionName'), t('aiWorkflow.greeting'));
    setSessions(prev => [s, ...prev]);
    setActiveSessionId(s.id);
    setShowMenu(false);
  }, [t, interruptCurrentTurn]);

  const switchSession = useCallback((id: string) => {
    if (id !== activeSessionIdRef.current) {
      if (inFlightRef.current) interruptCurrentTurn();
    }
    setActiveSessionId(id);
    setShowMenu(false);
  }, [interruptCurrentTurn]);

  const deleteSession = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (id === activeSessionIdRef.current) {
      if (inFlightRef.current) interruptCurrentTurn();
    }
    const replacement = createSession(t('aiWorkflow.defaultSessionName'), t('aiWorkflow.greeting'));
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id);
      if (next.length === 0) next.push(replacement);
      return next;
    });
    setActiveSessionId(prev => {
      if (prev === id) {
        const remaining = sessions.filter(s => s.id !== id);
        return remaining[0]?.id || replacement.id;
      }
      return prev;
    });
  }, [sessions, t, interruptCurrentTurn]);

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
    const sessionId = activeSessionId;
    const requestId = ++requestIdRef.current;
    const abortController = new AbortController();
    inFlightRef.current = abortController;
    setSending(true);
    const startedAt = Date.now();
    setNow(startedAt);
    setSessions(prev => prev.map(s => s.id === sessionId
      ? { ...s, turns: [...s.turns, { role: 'assistant', steps: [], streaming: true, startedAt, lastActivityAt: startedAt }] }
      : s));

    const updateTurn = (update: (turn: ChatTurn) => ChatTurn) => {
      if (requestIdRef.current !== requestId) return;
      setSessions(prev => prev.map(s => {
        if (s.id !== sessionId) return s;
        const turns = [...s.turns];
        const last = turns.length - 1;
        if (last < 0 || turns[last].role !== 'assistant' || !turns[last].streaming) return s;
        turns[last] = update(turns[last]);
        return { ...s, turns };
      }));
    };

    const history = historyTurns.map(turn => ({
      role: turn.role,
      content: turn.content || turn.steps?.filter(step => step.type === 'reply').map(step => step.content).join('\n') || '',
    }));
    try {
      let terminalError = false;
      await streamAIChat({
        message: userMsg,
        workflow,
        workflow_id: workflow.id || null,
        history,
        files: currentAttachments,
      }, event => {
        if (event.type === 'error') terminalError = true;
        const step: ChatStep = {
          ...event,
          workflow: event.workflow
            ? sanitizeWorkflow(event.workflow, workflow, t('common.untitled'))
            : undefined,
        };
        updateTurn(turn => ({
          ...turn,
          steps: appendChatStep(turn.steps || [], step),
          lastActivityAt: Date.now(),
        }));
      }, abortController.signal);
      updateTurn(turn => ({ ...turn, streaming: false, isError: terminalError }));
    } catch (err) {
      if (requestIdRef.current !== requestId) return;
      const stopped = abortController.signal.aborted || (err instanceof DOMException && err.name === 'AbortError');
      if (!stopped) logError('aiWorkflow.chat', err);
      let message = stopped ? t('aiWorkflow.generation.stopped') : err instanceof Error ? err.message : String(err);
      if (err instanceof ApiError) {
        const body = err.body;
        const detail = typeof body === 'string' ? body
          : body && typeof body === 'object'
            ? (body as Record<string, unknown>).error || (body as Record<string, unknown>).detail || (body as Record<string, unknown>).message
            : undefined;
        message = typeof detail === 'string' && detail.trim() ? detail.slice(0, 500)
          : err.status === 401 ? t('aiWorkflow.error.signIn')
            : err.status === 429 ? t('aiWorkflow.error.quota') : message;
      }
      updateTurn(turn => ({
        ...turn,
        streaming: false,
        isError: !stopped,
        steps: turn.steps?.some(step => step.type === 'error')
          ? turn.steps
          : [...(turn.steps || []), { type: stopped ? 'status' : 'error', content: message, status: stopped ? 'completed' : 'error' }],
      }));
    } finally {
      if (requestIdRef.current === requestId) {
        inFlightRef.current = null;
        setSending(false);
      }
    }
  }, [activeSessionId, turns, workflow, t]);

  const send = useCallback(async () => {
    if ((!input.trim() && attachments.length === 0) || sending) return;
    const userMsg = input.trim();
    setInput('');
    setSkillQuery(null);
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
      if (sending || inFlightRef.current) return;
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
    [onApplyWorkflow, activeSessionId, sending, t]
  );

  // --- Slash-command skill autocomplete -----------------------------------

  const handleInputChange = useCallback((value: string) => {
    setInput(value);
    if (value.startsWith('/')) {
      setSkillQuery(value.slice(1));
      setSkillIndex(0);
      if (!skillsCache) {
        // Best-effort: the dropdown simply stays empty when the fetch fails.
        loadSkills().then(setAvailableSkills).catch(() => { /* autocomplete unavailable */ });
      }
    } else if (skillQuery !== null) {
      setSkillQuery(null);
    }
  }, [skillQuery]);

  const selectSkill = useCallback((skill: SkillSummary) => {
    setInput(`/${skill.name} `);
    setSkillQuery(null);
  }, []);

  const handleInputKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (skillQuery !== null) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        setSkillQuery(null);
        return;
      }
      if (skillDropdownVisible) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setSkillIndex(i => Math.min(i + 1, skillMatches.length - 1));
          return;
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          setSkillIndex(i => Math.max(i - 1, 0));
          return;
        }
        if (e.key === 'Tab' || e.key === 'Enter') {
          e.preventDefault();
          const skill = skillMatches[Math.min(skillIndex, skillMatches.length - 1)];
          if (skill) selectSkill(skill);
          return;
        }
      }
    }
    if (e.key === 'Enter') send();
  }, [skillQuery, skillDropdownVisible, skillMatches, skillIndex, selectSkill, send]);

  // --- Drawer resize --------------------------------------------------------

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    resizeDragRef.current = { startX: e.clientX, startWidth: drawerWidth };
    setIsResizing(true);
    document.body.style.userSelect = 'none';
    const handleMove = (ev: MouseEvent) => {
      const drag = resizeDragRef.current;
      if (!drag) return;
      // The handle sits on the LEFT edge: dragging left grows the drawer.
      setDrawerWidth(clampDrawerWidth(drag.startWidth + (drag.startX - ev.clientX), window.innerWidth));
    };
    const handleUp = () => {
      resizeDragRef.current = null;
      setIsResizing(false);
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
  }, [drawerWidth]);

  // --- Shared JSX (drawer + pop-out render the same chat, same state) ------

  const sessionItems = sessions.map(s => (
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
  ));

  const renderHeader = (inPopout: boolean) => (
    <div className="ai-drawer-header">
      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {!inPopout && (
          <button
            className="btn btn-icon btn-sm"
            onClick={() => setShowMenu(!showMenu)}
            title={t('aiWorkflow.sessions.openTitle')}
          >
            <Icon name="menu" size={16} />
          </button>
        )}
        <Icon name="wand" size={16} /> {t('aiWorkflow.title')}
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button
          className="btn btn-icon btn-sm"
          onClick={() => setIsPoppedOut(!inPopout)}
          title={inPopout ? t('aiWorkflow.popout.dockTitle') : t('aiWorkflow.popout.openTitle')}
        >
          <Icon name={inPopout ? 'minimize' : 'maximize'} size={14} />
        </button>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('common.close')}>
          <Icon name="close" size={14} />
        </button>
      </span>
    </div>
  );

  const chatBody = (
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
              <div className={`ai-msg assistant ${turn.isError ? 'ai-error' : ''}`}>
                {turn.isError && !turn.steps?.length ? (
                  <>
                    <Icon name="warning" size={14} className="ai-error-icon" />
                    <div className="ai-error-text">
                      <div>{t('aiWorkflow.error.backend', { message: turn.content || '' })}</div>
                      <div className="ai-error-hint">{t('aiWorkflow.error.hint')}</div>
                    </div>
                  </>
                ) : turn.steps ? (
                  <div className="ai-steps">
                    {turn.streaming && (
                      <div className="ai-activity-summary" role="status">
                        <span className="ai-spinner" />
                        <span>{turn.steps.length ? t('aiWorkflow.generation.active') : t('aiWorkflow.generation.queued')}</span>
                        <span>{t('aiWorkflow.generation.elapsed', { seconds: Math.max(0, Math.floor((now - (turn.startedAt || now)) / 1000)) })}</span>
                        <span>{t('aiWorkflow.generation.lastActivity', { seconds: Math.max(0, Math.floor((now - (turn.lastActivityAt || now)) / 1000)) })}</span>
                        <button className="btn btn-sm btn-ghost" onClick={stop} title={t('aiWorkflow.generation.stopTitle')}>
                          {t('aiWorkflow.generation.stop')}
                        </button>
                      </div>
                    )}
                    {turn.steps.map((step, si) => (
                      <StepRenderer
                        key={si}
                        step={step}
                        onApply={handleApply}
                        applyDisabled={sending}
                        statusOutcome={step.type === 'status' && step.status === 'running'
                          ? (() => {
                              const later = turn.steps?.slice(si + 1) || [];
                              if (later.some(next => ['commentary', 'tool_call', 'reply', 'propose_changes'].includes(next.type))) return 'received';
                              if (later.some(next => next.type === 'error')) return 'error';
                              return turn.streaming ? undefined : 'ended';
                            })()
                          : undefined}
                        toolOutcome={step.type === 'tool_call'
                          ? (() => {
                              const result = turn.steps?.find(later => later.type === 'tool_result' && later.id && later.id === step.id);
                              return result ? toolResultState(result) : undefined;
                            })()
                          : undefined}
                      />
                    ))}
                    {!turn.streaming && !turn.isError && turn.model && <div className="ai-model-badge">{turn.model}</div>}
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
        <div ref={bottomRef} />
      </div>
    </div>
  );

  const chatFooter = (
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
            ↻ {t(turns[turns.length - 1].isError ? 'aiWorkflow.generation.retry' : 'aiWorkflow.generation.regenerate')}
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
      {skillDropdownVisible && (
        <div className="ai-skill-dropdown nodrag" role="listbox" aria-label={t('aiWorkflow.skills.listLabel')}>
          {skillMatches.map((skill, i) => (
            <button
              key={skill.name}
              type="button"
              role="option"
              aria-selected={i === skillIndex}
              className={`ai-skill-option ${i === skillIndex ? 'active' : ''}`}
              onMouseDown={e => e.preventDefault()}
              onClick={() => selectSkill(skill)}
              onMouseEnter={() => setSkillIndex(i)}
            >
              <span className="ai-skill-name">/{skill.name}</span>
              <span className="ai-skill-desc">{skill.description}</span>
            </button>
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
          onChange={e => handleInputChange(e.target.value)}
          onKeyDown={handleInputKeyDown}
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
  );

  if (isPoppedOut) {
    return (
      <div className="ai-popout-backdrop" onClick={() => setIsPoppedOut(false)}>
        <div
          className="ai-popout"
          role="dialog"
          aria-modal="true"
          aria-label={t('aiWorkflow.title')}
          onClick={e => e.stopPropagation()}
        >
          {renderHeader(true)}
          <div className="ai-popout-content">
            <aside className="ai-popout-sidebar">
              <div className="ai-session-menu-header">
                <strong>{t('aiWorkflow.sessions.menuTitle')}</strong>
                <button className="btn btn-primary btn-sm" onClick={createNewSession}>
                  <Icon name="plus" size={12} /> {t('aiWorkflow.sessions.newSession')}
                </button>
              </div>
              <div className="ai-session-list">{sessionItems}</div>
            </aside>
            <div className="ai-popout-main">
              {chatBody}
              {chatFooter}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`ai-drawer ${isResizing ? 'ai-drawer-resizing' : ''}`}
      style={viewportWidth > DRAWER_FULL_WIDTH_BREAKPOINT ? { width: drawerWidth } : undefined}
      onClick={e => e.stopPropagation()}
    >
      <div className="ai-drawer-resize-handle" onMouseDown={startResize} />

      {/* Header */}
      {renderHeader(false)}

      {/* Session Menu Dropdown */}
      {showMenu && (
        <div className="ai-session-menu" ref={menuRef}>
          <div className="ai-session-menu-header">
            <strong>{t('aiWorkflow.sessions.menuTitle')}</strong>
            <button className="btn btn-primary btn-sm" onClick={createNewSession}>
              <Icon name="plus" size={12} /> {t('aiWorkflow.sessions.newSession')}
            </button>
          </div>
          <div className="ai-session-list">{sessionItems}</div>
        </div>
      )}

      {/* Body */}
      {chatBody}

      {/* Footer */}
      {chatFooter}
    </div>
  );
}

function StepRenderer({ step, onApply, toolOutcome, applyDisabled, statusOutcome }: { step: ChatStep; onApply: (wf: Workflow) => void; toolOutcome?: string; applyDisabled?: boolean; statusOutcome?: 'received' | 'error' | 'ended' }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  switch (step.type) {
    case 'status':
      return <div className="ai-step-status">
        <Icon name={statusOutcome === 'received' ? 'check' : statusOutcome === 'error' ? 'warning' : 'clock'} size={12} />
        {statusOutcome === 'received' ? t('aiWorkflow.steps.modelReceived')
          : statusOutcome === 'error' ? t('aiWorkflow.steps.modelFailed')
            : statusOutcome === 'ended' ? t('aiWorkflow.steps.modelEnded') : step.content}
      </div>;

    case 'commentary':
      return <div className="ai-step-commentary">
        <strong>{t('aiWorkflow.steps.assistantUpdate')}</strong>
        <div className="ai-markdown" dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(step.content) }} />
      </div>;

    case 'error':
      return <div className="ai-step-error" role="alert">
        <Icon name="warning" size={12} /> {t('aiWorkflow.error.backend', { message: step.content })}
        <div className="ai-error-hint">{t('aiWorkflow.error.hint')}</div>
      </div>;

    case 'thinking':
      return (
        <div className="ai-step-thinking">
          <button className="ai-step-toggle" onClick={() => setExpanded(!expanded)}>
            <Icon name="lightbulb" size={12} />
            {expanded ? t('aiWorkflow.steps.hideActivity') : t('aiWorkflow.steps.showActivity')}
          </button>
          {expanded && <pre className="ai-step-pre">{step.content}</pre>}
        </div>
      );

    case 'tool_call':
      return (
        <div className="ai-step-tool-call">
          <button className="ai-step-header ai-step-expand" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
            <Icon name="settings" size={12} />
            <span className="ai-step-name" title={step.name}>{displayToolName(step.name, t('aiWorkflow.steps.tool'))}</span>
            <span className="ai-step-state">{t(toolOutcome === 'cancelled' ? 'aiWorkflow.steps.cancelled' : toolOutcome === 'error' ? 'aiWorkflow.steps.failed' : toolOutcome ? 'aiWorkflow.steps.completed' : 'aiWorkflow.steps.running')}</span>
          </button>
          {expanded && <pre className="ai-step-pre">{JSON.stringify(step.arguments, null, 2)}</pre>}
        </div>
      );

    case 'tool_result':
      return (
        <div className={`ai-step-tool-result ${step.status === 'error' ? 'failed' : ''}`}>
          <button className="ai-step-header ai-step-expand" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
            <Icon name={toolResultState(step) === 'completed' ? 'check' : 'warning'} size={12} />
            <span className="ai-step-name" title={step.name}>{t('aiWorkflow.steps.toolResult', { name: displayToolName(step.name, t('aiWorkflow.steps.tool')) })}</span>
            <span className="ai-step-state">{t(toolResultState(step) === 'cancelled' ? 'aiWorkflow.steps.cancelled' : toolResultState(step) === 'error' ? 'aiWorkflow.steps.failed' : 'aiWorkflow.steps.completed')}</span>
            {typeof step.duration_ms === 'number' && <span>{(step.duration_ms / 1000).toFixed(1)}s</span>}
          </button>
          {expanded && <pre className="ai-step-pre">{JSON.stringify(step.result, null, 2)}</pre>}
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
              <button className="btn btn-primary btn-sm" disabled={applyDisabled} onClick={() => onApply(step.workflow!)}>
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
    case 'reply_delta':
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
