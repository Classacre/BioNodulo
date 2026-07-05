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
  /** Update a node param from an on-node widget. `history` (default true) pushes
   *  an undo entry — pass false for continuous input (slider drag) and true on
   *  release. */
  setParam: (id: string, key: string, value: unknown, history?: boolean) => void;
  /** Set a node's display colour (ui.color) from the toolbar colour picker. */
  setColor: (id: string, color: string) => void;
  /** Dissolve a group node, keeping its children (clears their parentId). */
  ungroup: (groupId: string) => void;
  /** Delete a group node AND its children. */
  deleteGroup: (groupId: string) => void;
  /** Open the comment thread popover for a node. Undefined when collab is off. */
  comment?: (id: string) => void;
  /** Toggle a boolean ui flag (muted / bypassed / pinned / output). */
  toggleFlag: (id: string, flag: 'muted' | 'bypassed' | 'pinned' | 'output') => void;
  /** Open the node info / edit-properties dialog. */
  openProperties: (id: string) => void;
  /** Show/hide a param's input dot ("Add input"). Hiding also drops any edge
   *  feeding it. The widget itself always stays. */
  togglePromotedInput: (id: string, key: string) => void;
  /** Set the exact set of params showing an input dot (the "All" toggle).
   *  Passing [] clears them; keys removed here also lose their feeding edges. */
  setPromotedInputs: (id: string, keys: string[]) => void;
}

export const BioNodeActionsContext = createContext<BioNodeActions | null>(null);

// True while more than one node is selected. Nodes read this to hide their own
// per-node toolbar during a multi-select (the canvas shows one shared toolbar).
export const MultiSelectContext = createContext(false);
