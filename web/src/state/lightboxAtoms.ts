import { atom } from 'jotai';

export interface LightboxImage {
  src: string;
  alt: string;
  filename: string;
}

export interface HtmlPreviewState {
  src: string;
  filename: string;
}

export const lightboxOpenAtom = atom(false);
export const lightboxImagesAtom = atom<LightboxImage[]>([]);
export const lightboxIndexAtom = atom(0);
export const htmlPreviewStateAtom = atom<HtmlPreviewState | null>(null);

export const openLightboxAtom = atom(
  null,
  (_get, set, payload: { images: LightboxImage[]; index: number }) => {
    set(lightboxImagesAtom, payload.images);
    set(lightboxIndexAtom, payload.index);
    set(lightboxOpenAtom, true);
  },
);
