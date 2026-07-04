import { createContext } from 'react';

// Actions the on-node toolbar (native React Flow <NodeToolbar>) dispatches back
// to the canvas. Passed via context — NOT via each node's `data` — so node data
// stays value-stable and the memoized <BioNode> does not re-render every frame
// of a drag just because a fresh callback identity landed in its props.
export interface BioNodeActions {
  run: (id: string) => void;
  rename: (id: string) => void;
  duplicate: (id: string) => void;
  toggleCollapse: (id: string) => void;
  remove: (id: string) => void;
  /** Commit a native <NodeResizer> resize back to the workflow node's ui. */
  resize: (id: string, width: number, height: number) => void;
  /** Dissolve a group node, keeping its children (clears their parentId). */
  ungroup: (groupId: string) => void;
  /** Delete a group node AND its children. */
  deleteGroup: (groupId: string) => void;
}

export const BioNodeActionsContext = createContext<BioNodeActions | null>(null);
