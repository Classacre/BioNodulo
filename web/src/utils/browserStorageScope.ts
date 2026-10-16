export interface BrowserStorageConfig {
  editorMode?: boolean;
  cloudMode?: boolean;
  user?: { id?: string } | null;
  team?: { id?: string } | null;
}

export interface BrowserStorageScope {
  mode: 'local' | 'cloud' | 'blocked';
  storageSuffix: string | null;
  identity: string;
}

export const LOCAL_BROWSER_STORAGE_SCOPE: BrowserStorageScope = Object.freeze({
  mode: 'local', storageSuffix: '', identity: 'local',
});

const encode = (value: string) => encodeURIComponent(value).replace(/\./g, '%2E');

/** Unattributed legacy content belongs only to explicit local/desktop mode. */
export function resolveBrowserStorageScope(
  config: BrowserStorageConfig | null | undefined,
  nonMemberInvite = false,
): BrowserStorageScope {
  const user = config?.user?.id || '';
  const team = config?.team?.id || '';
  if (!nonMemberInvite && config?.editorMode === false && config.cloudMode === false) {
    return LOCAL_BROWSER_STORAGE_SCOPE;
  }
  if (!nonMemberInvite && (config?.editorMode || config?.cloudMode) && user && team) {
    const storageSuffix = `.cloud.${encode(user)}.${encode(team)}`;
    return { mode: 'cloud', storageSuffix, identity: storageSuffix };
  }
  return { mode: 'blocked', storageSuffix: null,
    identity: `blocked.${encode(user)}.${encode(team)}.${nonMemberInvite ? 'invite' : 'unknown'}` };
}

export function browserStorageKey(base: string, scope: BrowserStorageScope): string | null {
  return scope.storageSuffix === null ? null : `${base}${scope.storageSuffix}`;
}
