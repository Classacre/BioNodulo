import { createContext } from 'react';

// Actions the custom <BioEdge> dispatches back to the canvas (e.g. its native
// EdgeLabelRenderer delete button). Passed via context so edge data stays stable.
export interface BioEdgeActions {
  removeEdge: (id: string) => void;
}

export const BioEdgeActionsContext = createContext<BioEdgeActions | null>(null);
