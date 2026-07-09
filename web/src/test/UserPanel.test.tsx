// web/src/test/UserPanel.test.tsx
import { render, screen } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { authUserAtom, cloudConfigAtom } from '../state/appAtoms';
import UserPanel from '../components/panels/UserPanel';

vi.mock('../hooks/cloud/useClerkAuth', () => ({
  useClerkAuth: () => ({ clerkEnabled: false, clerkSignedIn: false, openSignIn: vi.fn(), openProfile: vi.fn(), openOrganization: vi.fn(), signOut: vi.fn() }),
}));
vi.mock('../hooks/cloud/useDesktopAuth', () => ({
  useDesktopAuth: () => ({ available: false, signInViaBrowser: vi.fn(), pending: false, cancel: vi.fn() }),
}));

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
