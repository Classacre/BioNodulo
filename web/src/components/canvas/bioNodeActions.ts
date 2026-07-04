import { createContext } from 'react';

// Actions the on-node toolbar (native React Flow <NodeToolbar>) dispatches back
// to the canvas. Passed via context — NOT via each node's `data` — so node data
// stays value-stable and the memoized <BioNode> does not re-render every frame
// of a drag just because a fresh callback identity landed in its props.
export interface BioNodeActions {
  run: (id: string) => void;
  edit: (id: string) => void;
  rename: (id: string) => void;
  duplicate: (id: string) => void;
  toggleCollapse: (id: string) => void;
  remove: (id: string) => void;
}

export const BioNodeActionsContext = createContext<BioNodeActions | null>(null);
