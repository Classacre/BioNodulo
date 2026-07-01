// Vitest setup — runs before every test file.
import '@testing-library/jest-dom/vitest';

// jsdom lacks ResizeObserver, which @xyflow/react (React Flow) and the canvas
// host use to track element size. Provide a no-op polyfill so components that
// observe size render without throwing under the test DOM.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

// React Flow reads DOMMatrixReadOnly when applying viewport transforms; jsdom
// does not implement it. A minimal stub covering the properties React Flow
// reads keeps pane transforms from throwing.
if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
  class DOMMatrixReadOnlyStub {
    m22 = 1;
    constructor(transform?: string) {
      const match = transform?.match(/matrix\(([^)]+)\)/);
      if (match) {
        const parts = match[1].split(',').map(Number);
        if (parts.length === 6) this.m22 = parts[3];
      }
    }
  }
  globalThis.DOMMatrixReadOnly = DOMMatrixReadOnlyStub as unknown as typeof DOMMatrixReadOnly;
}
