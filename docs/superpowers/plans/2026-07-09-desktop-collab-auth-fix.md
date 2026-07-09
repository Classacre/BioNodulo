# Desktop Collab & Auth Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the desktop app's broken auth/collab UX (stale "test" login, missing sign-in button, "forbidden" share link) and make a shared collab link actually work across machines by routing it through a cloud landing page backed by a bundled Cloudflare tunnel.

**Architecture:** Two independently shippable parts. **Part A** (local, web-only) fixes identity + the account menu + self-healing auth so a signed-out user can always set a name or sign in and can create a link without a 403. **Part B** (multi-repo) makes cross-machine sharing real: on "create link" the host auto-starts a **bundled** `cloudflared` quick tunnel, builds a `cloud.bionodulo.com/j` landing link that carries the tunnel base + invite, and that landing page prompts name/sign-in, detects an installed app (deep link `bionodulo://open?…`), and otherwise redirects the recipient's browser to the tunnel URL (the host's own SPA, same-origin → the existing join-on-load path works).

**Tech Stack:** React 18 + TypeScript + Jotai + Vitest (`web/`), FastAPI + pytest (`bionodulo/`), Rust + Tauri 2 + cargo test (`desktop/src-tauri/`), Next.js (`../bionodulo-website/`), `cloudflared` quick tunnels.

## Global Constraints

- No `Co-Authored-By: Claude` trailer in any commit; no Claude attribution in any user-facing copy. (Verbatim from user feedback 2026-07-08.)
- App version stays `0.1.0-alpha.1` (npm) / `0.1.0a1` (PEP 440). Do not bump.
- `bionodulo.collab.enabled` default stays `false` (`web/src/hooks/settings/useSettings.ts:38`).
- Desktop backend runs in **local mode** (no `BIONODULO_EDITOR_MODE`), so `/auth/token` anonymous minting is allowed (`bionodulo/api/auth_routes.py:35`). Do not change that default.
- Deep-link scheme is `bionodulo://`, allowed hosts `["open","desktop-auth"]` only (`desktop/src-tauri/src/security.rs:38`). Reuse `open`; do not add new hosts unless a task says so.
- Webview navigation is locked to the loopback backend origin + local pages (`desktop/src-tauri/src/security.rs:8`). Do NOT navigate the main window to a remote origin; cross-machine transport goes through the collab REST/WS base, not window navigation.
- Cloud host default: `https://cloud.bionodulo.com`. Introduce it as build-time `VITE_CLOUD_HOST` with that default.
- cloudflared is **bundled** with the app (user decision), exposed to the backend via `BIONODULO_CLOUDFLARED` (absolute path); backend falls back to `shutil.which("cloudflared")`.

---

# PART A — Local desktop auth/collab UX

Fully local, no network. Ship + test independently. Fixes reported issues 1 (test-by-default), 2 (no sign-in button), 3 (forbidden link when signed out).

## File Structure (Part A)

- `web/src/state/appAtoms.ts` — add `authKindAtom` (derived notion of guest vs account) is NOT needed; instead compute in UserPanel. Add nothing here unless a task says.
- `web/src/collab/authStorage.ts` — add `isGuestUser`/marking so a guest identity is distinguishable from a cloud account.
- `web/src/components/panels/UserPanel.tsx` — three states: signed-out (always actionable), guest, cloud account.
- `web/src/App.tsx` — self-heal 401 on collab create/join; add a "set display name" entry point; ensure signed-out create routes to AuthDialog.
- `web/src/collab/auth.ts` — export a `clearAuth()` convenience + a guest-mint helper reused by UserPanel.
- Tests: `web/src/test/UserPanel.test.tsx` (new), `web/src/test/authStorage.test.ts` (extend), `web/src/test/appCollabAuth.test.ts` (new, self-heal logic extracted to a pure helper).

### Task A1: Mark guest identities distinctly in storage

**Files:**
- Modify: `web/src/collab/authStorage.ts`
- Modify: `web/src/collab/types.ts` (add optional `kind` to `AuthUser`)
- Test: `web/src/test/authStorage.test.ts`

**Interfaces:**
- Produces: `AuthUser` gains `kind?: 'guest' | 'account'`. `setAuthUser(user)` persists `kind`. `getAuthUser()` returns it (default `'guest'` when a stored user has a token minted by `/auth/token`, `'account'` when set by OAuth/cloud). Helper `isGuestUser(u: AuthUser | null): boolean`.

- [ ] **Step 1: Write the failing test**

```ts
// web/src/test/authStorage.test.ts  (add to existing suite)
import { setAuthUser, getAuthUser, isGuestUser } from '../collab/authStorage';

it('round-trips the identity kind and defaults to guest', () => {
  setAuthUser({ id: 'u1', name: 'Ada', color: '#fff', kind: 'guest' });
  expect(getAuthUser()?.kind).toBe('guest');
  expect(isGuestUser(getAuthUser())).toBe(true);

  setAuthUser({ id: 'u2', name: 'Cloud', color: '#000', kind: 'account' });
  expect(isGuestUser(getAuthUser())).toBe(false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/… ` — N/A (web). Run: `cd web && npx vitest run src/test/authStorage.test.ts`
Expected: FAIL — `isGuestUser` is not exported; `kind` missing.

- [ ] **Step 3: Implement**

In `web/src/collab/types.ts`, add `kind?: 'guest' | 'account';` to the `AuthUser` interface.

In `web/src/collab/authStorage.ts`:

```ts
// getAuthUser(): include kind, defaulting to 'guest'
return {
  id: String(parsed.id),
  name: String(parsed.name),
  color: String(parsed.color || getUserColor(String(parsed.id))),
  kind: parsed.kind === 'account' ? 'account' : 'guest',
};
```

And append:

```ts
export function isGuestUser(user: { kind?: 'guest' | 'account' } | null): boolean {
  return !!user && user.kind !== 'account';
}
```

`setAuthUser` already `JSON.stringify`s the whole object, so `kind` persists with no change.

- [ ] **Step 4: Run tests**

Run: `cd web && npx vitest run src/test/authStorage.test.ts`
Expected: PASS

- [ ] **Step 5: Tag mint sites.** In `web/src/collab/auth.ts` `fetchToken`, set `kind: 'guest'` on the returned user. In `web/src/hooks/cloud/desktopOAuth.ts` `applyTokens`, set `kind: 'account'` on the user it stores. In `web/src/hooks/cloud/useCloudConfig.ts`, the injected cloud user gets `kind: 'account'`.

- [ ] **Step 6: Commit**

```bash
git add web/src/collab/authStorage.ts web/src/collab/types.ts web/src/collab/auth.ts web/src/hooks/cloud/desktopOAuth.ts web/src/hooks/cloud/useCloudConfig.ts web/src/test/authStorage.test.ts
git commit -m "feat(auth): distinguish guest vs cloud-account identities"
```

### Task A2: Account menu — always actionable, guest state, local "set name"

**Files:**
- Modify: `web/src/components/panels/UserPanel.tsx`
- Modify: `web/src/state/uiAtoms.ts` (add `showAuthDialogAtom` re-export is already in appAtoms; instead add nothing — reuse `showAuthDialogAtom` from `appAtoms`)
- Test: `web/src/test/UserPanel.test.tsx` (new)

**Interfaces:**
- Consumes: `isGuestUser` (A1), `showAuthDialogAtom` (`web/src/state/appAtoms.ts`), `signOutOAuth` (`web/src/hooks/cloud/desktopOAuth.ts`).
- Produces: UserPanel renders one of three states. Signed-out ALWAYS shows at least one actionable button: "Set a display name" (opens AuthDialog) when no cloud sign-in is configured, plus cloud sign-in when available. Guest state shows "Signed in as guest · <name>", a "Sign in to BioNodulo Cloud"/"Sign in with browser" CTA when available, a "Change name" button (opens AuthDialog), and "Sign out". Account state unchanged from today.

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/test/UserPanel.test.tsx
import { render, screen } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { authUserAtom, cloudConfigAtom, showAuthDialogAtom } from '../state/appAtoms';
import UserPanel from '../components/panels/UserPanel';

function renderWith(store: ReturnType<typeof createStore>) {
  return render(<Provider store={store}><UserPanel onClose={() => {}} /></Provider>);
}

it('signed-out with no cloud config still offers a set-name action', () => {
  const store = createStore();
  store.set(authUserAtom, null);
  store.set(cloudConfigAtom, { cloudMode: false, editorMode: false, user: null, team: null, plan: null, credits: null, accountUrl: null, clerkPublishableKey: null, oauth: null });
  renderWith(store);
  expect(screen.getByRole('button', { name: /set a display name/i })).toBeInTheDocument();
});

it('guest identity shows guest label + change name + sign out', () => {
  const store = createStore();
  store.set(authUserAtom, { id: 'g1', name: 'Blue Fox', color: '#39f', kind: 'guest' });
  store.set(cloudConfigAtom, { cloudMode: false, editorMode: false, user: null, team: null, plan: null, credits: null, accountUrl: null, clerkPublishableKey: null, oauth: null });
  renderWith(store);
  expect(screen.getByText(/guest/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /change name/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/test/UserPanel.test.tsx`
Expected: FAIL — no "set a display name" button; guest label absent.

- [ ] **Step 3: Implement UserPanel changes**

At top of component add:
```tsx
import { showAuthDialogAtom } from '../../state/appAtoms';
import { isGuestUser } from '../../collab/authStorage';
// ...
const setShowAuthDialog = useSetAtom(showAuthDialogAtom);
const guest = isGuestUser(authUser) && !configUser && !clerkSignedIn;
```

Recompute `signedIn` to exclude a bare guest from the "cloud account" state:
```tsx
const hasCloudAccount = Boolean(configUser) || clerkSignedIn || (Boolean(authUser) && !isGuestUser(authUser));
```

Replace the signed-out `if (!signedIn)` guard with `if (!hasCloudAccount && !guest)` and, inside it, ALWAYS render a set-name button before the cloud options:
```tsx
<button className="btn btn-primary" onClick={() => setShowAuthDialog(true)}>
  <Icon name="user" size={14} /> {t('account.setNameAction', { defaultValue: 'Set a display name' })}
</button>
```
Keep the existing Clerk / browser-OAuth buttons AFTER it, and delete the dead `else` that renders only "Cloud is not available in this build" as the sole content (it may remain as a secondary hint line, not the only affordance).

Add a `guest` branch (before the account branch):
```tsx
if (guest) {
  return (
    <div className="rail-panel">
      {header}
      <div className="rail-panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="account-avatar">{(authUser?.name || '?').charAt(0).toUpperCase()}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>{t('account.guestTitle', { defaultValue: 'Signed in as guest' })}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>{authUser?.name}</div>
          </div>
        </div>
        {clerkEnabled ? (
          <button className="btn btn-primary" onClick={openSignIn}>
            <Icon name="user" size={14} /> {t('account.signIn', { defaultValue: 'Sign in to BioNodulo Cloud' })}
          </button>
        ) : oauthAvailable ? (
          <button className="btn btn-primary" onClick={signInViaBrowser}>
            <Icon name="link" size={14} /> {t('account.signInBrowser', { defaultValue: 'Sign in with browser' })}
          </button>
        ) : null}
        <button className="btn" onClick={() => setShowAuthDialog(true)}>
          <Icon name="edit" size={14} /> {t('account.changeName', { defaultValue: 'Change name' })}
        </button>
        <button className="btn account-signout" onClick={() => signOutOAuth()}>
          <Icon name="export" size={14} /> {t('account.signOut', { defaultValue: 'Sign out' })}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `cd web && npx vitest run src/test/UserPanel.test.tsx`
Expected: PASS

- [ ] **Step 5: Add i18n keys.** Add `account.setNameAction`, `account.guestTitle`, `account.changeName` to `web/src/i18n/locales/en.ts` and `es.ts` (Spanish: "Definir un nombre visible", "Sesión de invitado", "Cambiar nombre").

- [ ] **Step 6: Commit**

```bash
git add web/src/components/panels/UserPanel.tsx web/src/test/UserPanel.test.tsx web/src/i18n/locales/en.ts web/src/i18n/locales/es.ts
git commit -m "feat(account): guest state + always-actionable signed-out menu"
```

### Task A3: Signed-out by default — do not auto-adopt a stale guest token as an account

**Files:**
- Modify: `web/src/hooks/collab/useAuth.ts`
- Test: `web/src/test/useAuth.test.tsx` (new or extend)

**Interfaces:**
- Consumes: `initAuth` (`web/src/collab/auth.ts`).
- Produces: On boot, a stored guest token is restored ONLY when collab is enabled (unchanged), but a guest identity never suppresses the account-menu sign-in CTA (handled in A2). No behavior change when `collabEnabled` is false: `authUser` stays `null` → account menu shows signed-out. This task adds a regression test locking the "fresh launch = signed out" contract.

- [ ] **Step 1: Write the locking test**

```tsx
// web/src/test/useAuth.test.tsx
import { renderHook } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { authUserAtom } from '../state/appAtoms';
import { useAuth } from '../hooks/collab/useAuth';

it('fresh launch with collab disabled stays signed out', () => {
  const store = createStore();
  const wrapper = ({ children }: { children: React.ReactNode }) => <Provider store={store}>{children}</Provider>;
  renderHook(() => useAuth({ collabEnabled: false, settingsReady: true }), { wrapper });
  expect(store.get(authUserAtom)).toBeNull();
});
```

- [ ] **Step 2: Run test** — Run: `cd web && npx vitest run src/test/useAuth.test.tsx` — Expected: PASS already (this locks current behavior; if it FAILS, a prior boot path is seeding authUser — fix by removing that seed). Keep the test.

- [ ] **Step 3: Commit**

```bash
git add web/src/test/useAuth.test.tsx
git commit -m "test(auth): lock signed-out-by-default on fresh launch"
```

### Task A4: Self-heal a rejected token on collab create/join (fix "forbidden")

**Files:**
- Create: `web/src/collab/collabAuthRecovery.ts` (pure helper, unit-testable)
- Modify: `web/src/App.tsx` (`handleCreateCollabSession`, `handleJoinCollabSession`)
- Test: `web/src/test/collabAuthRecovery.test.ts` (new)

**Interfaces:**
- Produces: `isAuthRejection(err: unknown): boolean` — true for `ApiError` with status 401 or 403. `recoverAndReprompt(err, { clearToken, setAuthUser, requestCollabAuth, action })` — when `isAuthRejection(err)`, clears the stored token, nulls `authUser`, and calls `requestCollabAuth(action)` so the AuthDialog re-opens; returns `true` if it handled the error, else `false`.

- [ ] **Step 1: Write the failing test**

```ts
// web/src/test/collabAuthRecovery.test.ts
import { isAuthRejection, recoverAndReprompt } from '../collab/collabAuthRecovery';
import { ApiError } from '../api/client';

it('detects 401/403 as auth rejections', () => {
  expect(isAuthRejection(new ApiError('x', 401, 'Unauthorized', null))).toBe(true);
  expect(isAuthRejection(new ApiError('x', 403, 'Forbidden', null))).toBe(true);
  expect(isAuthRejection(new ApiError('x', 500, 'Server', null))).toBe(false);
  expect(isAuthRejection(new Error('net'))).toBe(false);
});

it('clears token and reprompts on auth rejection', () => {
  const calls: string[] = [];
  const handled = recoverAndReprompt(new ApiError('x', 401, 'Unauthorized', null), {
    clearToken: () => calls.push('clear'),
    setAuthUser: () => calls.push('null'),
    requestCollabAuth: () => calls.push('reprompt'),
    action: { type: 'create' },
  });
  expect(handled).toBe(true);
  expect(calls).toEqual(['clear', 'null', 'reprompt']);
});
```

- [ ] **Step 2: Run test** — Run: `cd web && npx vitest run src/test/collabAuthRecovery.test.ts` — Expected: FAIL (module missing).

- [ ] **Step 3: Implement `web/src/collab/collabAuthRecovery.ts`**

```ts
import { ApiError } from '../api/client';
import type { CollabLinkTarget } from './shareLinks';

export type CollabAuthAction = { type: 'create' } | { type: 'join'; target: CollabLinkTarget };

export function isAuthRejection(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 401 || err.status === 403);
}

export function recoverAndReprompt(
  err: unknown,
  deps: {
    clearToken: () => void;
    setAuthUser: (u: null) => void;
    requestCollabAuth: (action: CollabAuthAction) => void;
    action: CollabAuthAction;
  },
): boolean {
  if (!isAuthRejection(err)) return false;
  deps.clearToken();
  deps.setAuthUser(null);
  deps.requestCollabAuth(deps.action);
  return true;
}
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Wire into App.tsx.** In `handleCreateCollabSession`'s `catch (err)` (currently `App.tsx:676`), before the generic toast:
```ts
if (recoverAndReprompt(err, { clearToken, setAuthUser, requestCollabAuth, action: { type: 'create' } })) {
  set('bionodulo.collab.enabled', false);
  return;
}
```
Do the same in `handleJoinCollabSession`'s catch with `action: { type: 'join', target: joinTarget }`. Import `recoverAndReprompt`, `clearToken` (from `./collab/auth`), and `setAuthUser` = the jotai setter for `authUserAtom`.

- [ ] **Step 6: Run the web test suite** — Run: `cd web && npx vitest run` — Expected: PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add web/src/collab/collabAuthRecovery.ts web/src/test/collabAuthRecovery.test.ts web/src/App.tsx
git commit -m "fix(collab): self-heal rejected token instead of showing 'forbidden'"
```

### Task A5: Manual verification of Part A in the desktop app

- [ ] **Step 1:** `cd web && npm run build` then `cd ../desktop && npm run prepare:assets && BIONODULO_DEV=1 npm run tauri dev` (or a release build). Clear webview storage first to simulate a fresh install.
- [ ] **Step 2:** Confirm: launch shows **Not signed in** (account panel), with a **Set a display name** button.
- [ ] **Step 3:** Set a name → account panel shows **Signed in as guest · <name>** with Change name + Sign out.
- [ ] **Step 4:** Sign out → back to signed-out with the set-name button (NOT a dead "cloud unavailable" screen).
- [ ] **Step 5:** While signed out, click Share → Create link → the AuthDialog appears (name/guest), and after naming, a link is created with **no** "forbidden" error.
- [ ] **Step 6:** Commit any copy tweaks; Part A done.

---

# PART B — Cross-machine share link (cloud landing + bundled tunnel)

Depends on Part A. Spans `bionodulo/` (backend), `desktop/src-tauri/` (bundle + deep link), `web/` (host share flow + in-app remote join), and `../bionodulo-website/` (landing page).

## Architecture (Part B)

1. **Host creates link:** `handleCreateCollabSession` → `POST /api/collab/rooms` (invite token) → `POST /api/collab/tunnel` (starts bundled cloudflared → `https://<rand>.trycloudflare.com`). Build landing URL:
   `https://cloud.bionodulo.com/j#h=<tunnelBase>&w=<workflowId>&i=<inviteToken>` (fragment, so the tunnel/invite never hit cloud server logs). Copy it.
2. **Recipient opens landing** (`cloud.bionodulo.com/j`): reads the fragment; prompts a display name or sign-in; tries the deep link `bionodulo://open?h=<tunnelBase>&w=<id>&i=<token>` with a ~1.2s visibility-timeout to detect an installed app → shows **Open in BioNodulo app** and **Continue in browser**.
3. **Continue in browser:** `window.location = <tunnelBase>/?workflow=<id>&invite=<token>` → loads the **host's** SPA through the tunnel (same-origin to the tunnel) → the existing `readCollabLinkTarget` join-on-load path connects live. No CORS, no new editor deploy.
4. **Open in app:** deep link wakes the recipient's desktop app; a new web listener joins the room using `<tunnelBase>` as a **remote collab base** (REST + WS target the tunnel origin instead of loopback). Host backend CORS must allow the recipient's loopback origin + the cloud origin.

## File Structure (Part B)

- `bionodulo/api/collab_runtime_routes.py` — cloudflared path via `BIONODULO_CLOUDFLARED`.
- `bionodulo/server.py` — CORS: allow the cloud origin + a loopback regex when sharing.
- `desktop/src-tauri/scripts/prepare-cloudflared.mjs` — new: fetch cloudflared per-OS into `assets/cloudflared/<os>/`.
- `desktop/src-tauri/tauri.{linux,macos,windows}.conf.json` — bundle the cloudflared resource.
- `desktop/src-tauri/src/supervisor.rs` — pass `BIONODULO_CLOUDFLARED` + CORS origins to the backend.
- `desktop/package.json` — `prepare:assets` also runs prepare-cloudflared.
- `web/src/collab/shareLinks.ts` — `buildCloudLandingUrl(...)`.
- `web/src/App.tsx` — auto-tunnel on create; build landing link; deep-link listener → remote join.
- `web/src/collab/remoteBase.ts` — new: remote-collab-base atom + helper the collab REST/WS read.
- `web/src/api/client.ts` + `web/src/collab/yjsDoc.ts` (or wherever the WS URL is built) — honor the remote base for collab paths only.
- `../bionodulo-website/app/j/page.tsx` (+ small client component) — the landing page.
- Config: `web/.env`-style `VITE_CLOUD_HOST`; desktop build passes it.

### Task B1: Backend — use a bundled cloudflared path

**Files:**
- Modify: `bionodulo/api/collab_runtime_routes.py` (`_start_cloudflare_tunnel`)
- Test: `tests/api/test_collab_tunnel.py` (new)

**Interfaces:**
- Produces: `_resolve_cloudflared() -> str | None` — returns `BIONODULO_CLOUDFLARED` if it is an existing executable, else `shutil.which("cloudflared")`. `_start_cloudflare_tunnel` uses it.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_collab_tunnel.py
import os
from bionodulo.api.collab_runtime_routes import _resolve_cloudflared

def test_prefers_env_binary(tmp_path, monkeypatch):
    fake = tmp_path / "cloudflared"
    fake.write_text("#!/bin/sh\n"); os.chmod(fake, 0o755)
    monkeypatch.setenv("BIONODULO_CLOUDFLARED", str(fake))
    assert _resolve_cloudflared() == str(fake)

def test_falls_back_to_path(monkeypatch):
    monkeypatch.delenv("BIONODULO_CLOUDFLARED", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cloudflared" if name == "cloudflared" else None)
    assert _resolve_cloudflared() == "/usr/bin/cloudflared"
```

- [ ] **Step 2: Run test** — Run: `./.venv/bin/pytest tests/api/test_collab_tunnel.py -v` — Expected: FAIL (`_resolve_cloudflared` missing).

- [ ] **Step 3: Implement** in `collab_runtime_routes.py`:

```python
def _resolve_cloudflared() -> str | None:
    env = os.environ.get("BIONODULO_CLOUDFLARED", "").strip()
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env
    return shutil.which("cloudflared")
```
Replace `cloudflared = shutil.which("cloudflared")` (line 111) with `cloudflared = _resolve_cloudflared()`.

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bionodulo/api/collab_runtime_routes.py tests/api/test_collab_tunnel.py
git commit -m "feat(collab): resolve bundled cloudflared via BIONODULO_CLOUDFLARED"
```

### Task B2: Backend — CORS for cross-origin collab when sharing

**Files:**
- Modify: `bionodulo/server.py` (CORS block ~line 358-365)
- Test: `tests/test_cors_share.py` (new)

**Interfaces:**
- Produces: when `BIONODULO_CORS_ORIGINS` contains entries, CORS also allows loopback origins via `allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d+)?$"`. A new env `BIONODULO_CORS_ALLOW_LOOPBACK=1` (set by the desktop supervisor) enables the regex without weakening the default server.

- [ ] **Step 1: Read the current CORS block** (`bionodulo/server.py:358-370`) to get exact variable names.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_cors_share.py
from fastapi.testclient import TestClient
from server import create_app  # adjust import to the app factory

def test_loopback_and_cloud_allowed(monkeypatch):
    monkeypatch.setenv("BIONODULO_CORS_ORIGINS", "https://cloud.bionodulo.com")
    monkeypatch.setenv("BIONODULO_CORS_ALLOW_LOOPBACK", "1")
    app = create_app()
    client = TestClient(app)
    r = client.options("/api/config", headers={
        "Origin": "http://127.0.0.1:53211",
        "Access-Control-Request-Method": "GET",
    })
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:53211"
```

- [ ] **Step 3: Run test** — Run: `./.venv/bin/pytest tests/test_cors_share.py -v` — Expected: FAIL.

- [ ] **Step 4: Implement.** In the CORS block, when `BIONODULO_CORS_ALLOW_LOOPBACK` is truthy pass `allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d+)?$"` to `CORSMiddleware` alongside the explicit `allow_origins` list, keeping `allow_credentials=True`.

- [ ] **Step 5: Run test** — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bionodulo/server.py tests/test_cors_share.py
git commit -m "feat(collab): allow loopback origins for cross-machine collab"
```

### Task B3: Desktop — fetch + bundle cloudflared

**Files:**
- Create: `desktop/scripts/prepare-cloudflared.mjs`
- Modify: `desktop/package.json` (`prepare:assets` script)
- Modify: `desktop/src-tauri/tauri.linux.conf.json`, `tauri.macos.conf.json`, `tauri.windows.conf.json` (add resource)

**Interfaces:**
- Produces: `assets/cloudflared/<os>/cloudflared[.exe]` staged before `tauri build`; bundled as a Tauri resource; resolvable at runtime under the resources dir.

- [ ] **Step 1: Write `prepare-cloudflared.mjs`** mirroring `prepare-python.mjs`'s uv fetch (download from `https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-<os>-<arch>[.exe]`, `chmod 0o755` on unix, idempotent skip if present). Per-OS asset names: `cloudflared-linux-amd64`, `cloudflared-darwin-amd64.tgz` (extract), `cloudflared-windows-amd64.exe`. Pin a version via `BIONODULO_CLOUDFLARED_VERSION` (default a known-good tag, not `latest`, for reproducible builds).

- [ ] **Step 2:** In `desktop/package.json`, change `prepare:assets` to also run `node scripts/prepare-cloudflared.mjs`.

- [ ] **Step 3:** In each `tauri.<os>.conf.json`, add the platform's cloudflared path to `bundle.resources` (next to python/uv). Keep `desktop/src-tauri/tauri.conf.json` base resources = backend only (per existing split).

- [ ] **Step 4: Verify staging** — Run: `cd desktop && npm run prepare:assets && ls -la src-tauri/../assets/cloudflared/*/` — Expected: the binary exists and is executable.

- [ ] **Step 5: Commit**

```bash
git add desktop/scripts/prepare-cloudflared.mjs desktop/package.json desktop/src-tauri/tauri.linux.conf.json desktop/src-tauri/tauri.macos.conf.json desktop/src-tauri/tauri.windows.conf.json
git commit -m "build(desktop): bundle cloudflared for collab tunnels"
```

### Task B4: Desktop — pass cloudflared path + CORS origins to the backend

**Files:**
- Modify: `desktop/src-tauri/src/supervisor.rs` (env block ~line 149-151)
- Modify: `desktop/src-tauri/src/paths.rs` (add `cloudflared_path(app)`)
- Test: `desktop/src-tauri/src/paths.rs` unit test

**Interfaces:**
- Consumes: `paths::resources_root` (existing).
- Produces: `paths::cloudflared_path(&AppHandle) -> PathBuf`. Supervisor sets `.env("BIONODULO_CLOUDFLARED", …)`, `.env("BIONODULO_CORS_ALLOW_LOOPBACK", "1")`, and appends `https://cloud.bionodulo.com` to `BIONODULO_CORS_ORIGINS`.

- [ ] **Step 1: Write a paths test** asserting `cloudflared_path` ends with the platform binary name (`cloudflared` or `cloudflared.exe`) under the resources dir. Run: `cd desktop/src-tauri && cargo test paths -- --nocapture` — Expected: FAIL until implemented.

- [ ] **Step 2: Implement** `cloudflared_path` in `paths.rs` (dev → `dev_assets_root().join("cloudflared").join(os).join(bin)`, packaged → `resources_root(app).join("cloudflared").join(os).join(bin)`), matching the python/uv resolution pattern.

- [ ] **Step 3: Wire supervisor.** After the existing `.env("BIONODULO_CORS_ORIGINS", &url)` (line 151), append the cloud origin to `url` (e.g. build `format!("{url},https://cloud.bionodulo.com")`) and add:
```rust
.env("BIONODULO_CORS_ALLOW_LOOPBACK", "1")
.env("BIONODULO_CLOUDFLARED", paths::cloudflared_path(app).to_string_lossy().to_string())
```
Guard with `if path.exists()` so a missing binary doesn't set a bad env.

- [ ] **Step 4: Run** — `cd desktop/src-tauri && cargo test` — Expected: PASS (all, incl. existing 10).

- [ ] **Step 5: Commit**

```bash
git add desktop/src-tauri/src/supervisor.rs desktop/src-tauri/src/paths.rs
git commit -m "feat(desktop): expose cloudflared + cloud CORS origin to backend"
```

### Task B5: Web — remote collab base plumbing

**Files:**
- Create: `web/src/collab/remoteBase.ts`
- Modify: `web/src/api/client.ts` (collab paths honor a remote base)
- Modify: the collab WebSocket URL builder (`web/src/collab/yjsDoc.ts` or `useCollab.ts` — locate the `ws://`/`wss://` construction)
- Test: `web/src/test/remoteBase.test.ts` (new)

**Interfaces:**
- Produces: `collabRemoteBaseAtom` (jotai, `string | null`). `setCollabRemoteBase(base)` / `getCollabRemoteBase()`. `resolveCollabUrl(path: string): string` — if a remote base is set AND `path` is a `/api/collab/*` or collab `ws` path, returns `<remoteBase>` + path; else same-origin. REST client and WS builder call `resolveCollabUrl` for collab endpoints only (never for `/api/config`, runs, object_info, etc.).

- [ ] **Step 1: Write the failing test**

```ts
// web/src/test/remoteBase.test.ts
import { setCollabRemoteBase, resolveCollabUrl } from '../collab/remoteBase';

it('rewrites only collab paths when a remote base is set', () => {
  setCollabRemoteBase('https://x.trycloudflare.com');
  expect(resolveCollabUrl('/api/collab/rooms/join')).toBe('https://x.trycloudflare.com/api/collab/rooms/join');
  expect(resolveCollabUrl('/api/config')).toBe('/api/config'); // untouched
  setCollabRemoteBase(null);
  expect(resolveCollabUrl('/api/collab/rooms/join')).toBe('/api/collab/rooms/join');
});
```

- [ ] **Step 2: Run** — `cd web && npx vitest run src/test/remoteBase.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement `remoteBase.ts`** with a module-scoped variable (so non-React callers like the API client can read it) plus a jotai atom kept in sync:
```ts
let remoteBase: string | null = null;
export function setCollabRemoteBase(base: string | null) { remoteBase = base ? base.replace(/\/+$/, '') : null; }
export function getCollabRemoteBase() { return remoteBase; }
const COLLAB_RE = /^\/?api\/collab\//;
export function resolveCollabUrl(path: string): string {
  if (!remoteBase) return path;
  const clean = path.replace(/^\/+/, '');
  return COLLAB_RE.test('/' + clean) ? `${remoteBase}/${clean}` : path;
}
```

- [ ] **Step 4:** In `web/src/api/client.ts` `buildUrl`, when `EDITOR_API_BASE` is unset and the path is a collab path, delegate to `resolveCollabUrl`. In the WS builder, prefix the collab ws path with the remote base's `ws(s)://` host when a remote base is set.

- [ ] **Step 5: Run** — `cd web && npx vitest run src/test/remoteBase.test.ts` — Expected: PASS. Then full `npx vitest run` — Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add web/src/collab/remoteBase.ts web/src/api/client.ts web/src/collab/yjsDoc.ts web/src/test/remoteBase.test.ts
git commit -m "feat(collab): optional remote base for cross-machine rooms"
```

### Task B6: Web — auto-tunnel on create + build cloud landing link

**Files:**
- Modify: `web/src/collab/shareLinks.ts` (add `buildCloudLandingUrl`)
- Modify: `web/src/App.tsx` (`handleCreateCollabSession`)
- Test: `web/src/test/shareLinks.test.ts` (extend)

**Interfaces:**
- Consumes: `VITE_CLOUD_HOST` (default `https://cloud.bionodulo.com`).
- Produces: `buildCloudLandingUrl({ cloudHost, tunnelBase, workflowId, inviteToken }): string` → `${cloudHost}/j#h=<enc>&w=<enc>&i=<enc>`.

- [ ] **Step 1: Write the failing test**

```ts
// web/src/test/shareLinks.test.ts (add)
import { buildCloudLandingUrl } from '../collab/shareLinks';
it('builds a fragment-based cloud landing link', () => {
  const u = buildCloudLandingUrl({ cloudHost: 'https://cloud.bionodulo.com', tunnelBase: 'https://x.trycloudflare.com', workflowId: 'wf1', inviteToken: 'tok' });
  expect(u).toBe('https://cloud.bionodulo.com/j#h=https%3A%2F%2Fx.trycloudflare.com&w=wf1&i=tok');
});
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement** `buildCloudLandingUrl` in `shareLinks.ts` using `encodeURIComponent` for each value.

- [ ] **Step 4:** In `handleCreateCollabSession` (`App.tsx`), after creating the room, when NOT `CLOUD_COLLAB` and running in the desktop app: `POST /api/collab/tunnel` to get `public_url`; if present, set the copied link to `buildCloudLandingUrl(...)` with `tunnelBase = public_url`; otherwise fall back to the existing same-origin link with the existing "local link only" warning. Keep the copy-to-clipboard + ShareDialog behavior.

- [ ] **Step 5: Run** — `cd web && npx vitest run src/test/shareLinks.test.ts` — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/collab/shareLinks.ts web/src/App.tsx web/src/test/shareLinks.test.ts
git commit -m "feat(collab): host builds cloud landing link over an auto tunnel"
```

### Task B7: Web — deep-link listener → in-app remote join

**Files:**
- Create: `web/src/hooks/collab/useDeepLinkJoin.ts`
- Modify: `web/src/App.tsx` (mount the hook)
- Test: `web/src/test/useDeepLinkJoin.test.ts` (new — test the pure param→action mapper)

**Interfaces:**
- Consumes: Tauri global event `app:deep-link` (payload `{ host, path, params }`) via `window.__TAURI__.event.listen` (guarded — no-op in browser). `setCollabRemoteBase` (B5), `parseCollabLinkTarget`/join handler (App).
- Produces: `deepLinkToJoin(payload): { remoteBase: string; target: CollabLinkTarget } | null` — for `host === 'open'` with `params.w`, returns `{ remoteBase: params.h, target: { workflowId: params.w, inviteToken: params.i ?? null } }`; else `null`.

- [ ] **Step 1: Write the failing test**

```ts
// web/src/test/useDeepLinkJoin.test.ts
import { deepLinkToJoin } from '../hooks/collab/useDeepLinkJoin';
it('maps an open deep link with a tunnel host to a remote join', () => {
  expect(deepLinkToJoin({ host: 'open', path: '/', params: { h: 'https://x.trycloudflare.com', w: 'wf1', i: 'tok' } }))
    .toEqual({ remoteBase: 'https://x.trycloudflare.com', target: { workflowId: 'wf1', inviteToken: 'tok' } });
  expect(deepLinkToJoin({ host: 'desktop-auth', path: '/', params: {} })).toBeNull();
});
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement** `deepLinkToJoin` + a `useDeepLinkJoin()` hook that, on `app:deep-link`, calls `deepLinkToJoin`; if non-null, `setCollabRemoteBase(remoteBase)` then triggers the join (reuse `handleJoinCollabSession(target)` — which will prompt name if signed out, per Part A). Validate `remoteBase` is `https://` and host ends with `.trycloudflare.com` (defense-in-depth) before using it.

- [ ] **Step 4:** Mount `useDeepLinkJoin()` in `App.tsx`.

- [ ] **Step 5: Run** — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/hooks/collab/useDeepLinkJoin.ts web/src/App.tsx web/src/test/useDeepLinkJoin.test.ts
git commit -m "feat(collab): join a remote room from a bionodulo://open deep link"
```

### Task B8: Website — the `/j` cloud landing page

**Files:**
- Create: `../bionodulo-website/apps/web/app/j/page.tsx` (adjust to the repo's app dir) + a `JoinClient.tsx` client component
- Test: `../bionodulo-website/.../j/JoinClient.test.tsx` (if the website has a test runner; else a manual check step)

**Interfaces:**
- Reads `location.hash` → `{ h, w, i }`. Renders: a display-name field / sign-in, an **Open in BioNodulo app** button, and a **Continue in browser** button.

- [ ] **Step 1:** Read the website's app-router layout + existing auth (Clerk) usage to match patterns. (`../bionodulo-website`.)

- [ ] **Step 2: Implement `JoinClient.tsx`:**
  - Parse the fragment (never send `h`/`i` to any server).
  - **Open in app:** set `window.location.href = 'bionodulo://open?h='+enc(h)+'&w='+enc(w)+'&i='+enc(i)`; start a `visibilitychange`/blur timer (~1200ms). If the page hides → app opened; else surface "App not detected — install or continue in browser."
  - **Continue in browser:** `window.location.href = h + '/?workflow=' + enc(w) + '&invite=' + enc(i)` (the host's SPA via tunnel; existing join-on-load runs there).
  - Name/sign-in: reuse the site's Clerk sign-in; a name is optional (guest join happens on the host SPA / app side).
- [ ] **Step 3:** `page.tsx` renders `<JoinClient/>` (client component; the route is static/SSR-safe since all data is in the fragment).
- [ ] **Step 4: Manual check:** run the website locally, open `/j#h=https://example.com&w=wf1&i=tok`, verify both buttons build the right URLs (inspect, don't navigate).
- [ ] **Step 5: Commit** (in the website repo)

```bash
cd ../bionodulo-website && git add apps/web/app/j && git commit -m "feat(web): collab join landing page (open-in-app + browser fallback)"
```

### Task B9: End-to-end verification across two machines

- [ ] **Step 1:** Build the desktop app with bundled cloudflared (`npm run prepare:assets && npm run tauri build`). Install on machine A (host) and machine B (recipient).
- [ ] **Step 2:** Deploy the website `/j` route (or run a preview) so `cloud.bionodulo.com/j` resolves. If not yet deployable, temporarily set `VITE_CLOUD_HOST` to a reachable preview URL for the test.
- [ ] **Step 3:** On A: set a display name, Share → Create link. Confirm a `cloud.bionodulo.com/j#…` link is copied and a tunnel started (check the toast says a public link is ready).
- [ ] **Step 4:** On B **without** the app: open the link in a browser → landing page → **Continue in browser** → the host's editor loads via the tunnel and shows a live cursor/edit from A. ✅ issue 4 fixed (browser path).
- [ ] **Step 5:** On B **with** the app: open the link → **Open in BioNodulo app** → the desktop app joins the room live via the tunnel (remote base). ✅ open-in-app path.
- [ ] **Step 6:** Record results in the migration memory + close out.

---

## Self-Review notes

- **Spec coverage:** issue 1 → A2/A3; issue 2 → A2; issue 3 → A4 (+ A2 always-actionable); issue 4 → B1–B9; "point to cloud editor" → B6/B8; "prompt name or sign in" → B8 + A2; "detect install + open in app" → B7/B8; "bundle cloudflared" → B3/B4.
- **Loopback nav lock:** respected — the browser fallback redirects to the tunnel (a NEW browser tab/origin), not the desktop main window; in-app join uses the remote collab base, not window navigation.
- **Security:** deep-link host stays `open`; `remoteBase` validated to `https://*.trycloudflare.com`; CORS opens loopback + the single cloud origin only when `BIONODULO_CORS_ALLOW_LOOPBACK=1` (set by desktop supervisor only).
- **Known limitation to tell the user:** trycloudflare quick-tunnel URLs are ephemeral (die when the host app closes / rotates per session); the link is good only while the host is running and sharing. A stable named tunnel or the unblocked cloud-collab (Phase 3) would remove that; out of scope here.
