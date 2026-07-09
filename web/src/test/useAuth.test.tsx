import { renderHook } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import type { ReactNode } from 'react';
import { authUserAtom } from '../state/appAtoms';
import { useAuth } from '../hooks/collab/useAuth';

it('fresh launch with collab disabled stays signed out', () => {
  const store = createStore();
  const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
  renderHook(() => useAuth({ collabEnabled: false, settingsReady: true }), { wrapper });
  expect(store.get(authUserAtom)).toBeNull();
});
