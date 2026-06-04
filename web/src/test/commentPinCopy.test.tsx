import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() {
    return storage.size;
  },
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  removeItem: (key: string) => {
    storage.delete(key);
  },
  setItem: (key: string, value: string) => {
    storage.set(key, String(value));
  },
};

describe('CommentPin copy i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    await setLanguage('en');
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders pluralized comment titles from the active locale', async () => {
    const { default: CommentPin } = await import('../collab/CommentPin');
    const { setLanguage } = await import('../i18n');

    await setLanguage('es');

    render(
      <>
        <CommentPin commentCount={1} hasUnresolved={false} onClick={() => undefined} x={0} y={0} />
        <CommentPin commentCount={2} hasUnresolved onClick={() => undefined} x={20} y={0} />
      </>,
    );

    expect(screen.getByTitle('1 comentario')).toBeInTheDocument();
    expect(screen.getByTitle('2 comentarios (2 sin resolver)')).toBeInTheDocument();
  });

  it('keeps CommentPin tooltip copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../collab/CommentPin.tsx'), 'utf8');

    expect(source).toContain('collab.commentPinTitle');
    expect(source).not.toContain('commentCount !== 1');
    expect(source).not.toContain('unresolved)');
  });
});
