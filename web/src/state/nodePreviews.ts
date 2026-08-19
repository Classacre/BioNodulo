// Latest per-node run previews, published by App whenever the run history
// changes and read by BioNode to render inline output previews. Keyed by
// (root-level) node id.

import { atom } from 'jotai';
import type { NodePreviewRef } from '../utils/nodePreview';

export const nodePreviewsAtom = atom<Record<string, NodePreviewRef>>({});
