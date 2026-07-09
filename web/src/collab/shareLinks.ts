export interface CollabLinkTarget {
  workflowId: string;
  inviteToken?: string | null;
}

export const CLOUD_HOST = (import.meta.env.VITE_CLOUD_HOST || 'https://cloud.bionodulo.com').replace(/\/+$/, '');

export interface CloudLandingUrlOptions {
  cloudHost?: string;
  tunnelBase: string;
  workflowId: string;
  inviteToken: string;
}

export function buildCloudLandingUrl({ cloudHost = CLOUD_HOST, tunnelBase, workflowId, inviteToken }: CloudLandingUrlOptions): string {
  return `${cloudHost}/j#h=${encodeURIComponent(tunnelBase)}&w=${encodeURIComponent(workflowId)}&i=${encodeURIComponent(inviteToken)}`;
}

const WORKFLOW_ID_RE = /^[a-zA-Z0-9._:-]{1,160}$/;

export function buildCollabRoomUrl(workflowId: string, inviteToken?: string | null, baseUrl?: string | null): string {
  const url = new URL(baseUrl || window.location.href, window.location.href);
  url.hash = '';
  url.searchParams.set('workflow', workflowId);
  if (inviteToken) {
    url.searchParams.set('invite', inviteToken);
  } else {
    url.searchParams.delete('invite');
  }
  return url.toString();
}

export function readCollabLinkTarget(): CollabLinkTarget | null {
  if (typeof window === 'undefined') return null;
  return parseCollabLinkTarget(window.location.href);
}

export function parseCollabLinkTarget(input: string): CollabLinkTarget | null {
  const value = input.trim();
  if (!value) return null;

  try {
    const url = new URL(value, window.location.href);
    const workflowId = url.searchParams.get('workflow')?.trim() || '';
    if (WORKFLOW_ID_RE.test(workflowId)) {
      return {
        workflowId,
        inviteToken: url.searchParams.get('invite')?.trim() || null,
      };
    }
  } catch {
    // Fall through to raw room-id parsing.
  }

  if (WORKFLOW_ID_RE.test(value)) {
    return { workflowId: value, inviteToken: null };
  }
  return null;
}

export function clearCollabLinkParams(): void {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  const before = url.toString();
  url.searchParams.delete('workflow');
  url.searchParams.delete('invite');
  if (url.toString() !== before) {
    window.history.replaceState({}, '', url);
  }
}
