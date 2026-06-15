// Thin typed wrapper over the inline boot loader defined in index.html.
// The loader paints before the bundle is parsed; once React runs we update its
// progress/label and dismiss it when the app is interactive.

interface BootLoaderApi {
  setProgress: (value: number | null, label?: string) => void;
  done: () => void;
}

function loader(): BootLoaderApi | undefined {
  return (window as unknown as { __bnLoader?: BootLoaderApi }).__bnLoader;
}

/** Update the boot loader's bar (0–100) and/or status text. No-ops if the
 *  loader was already dismissed (e.g. on in-app remounts). */
export function bootProgress(value: number | null, label?: string): void {
  try {
    loader()?.setProgress(value, label);
  } catch {
    /* loader gone — ignore */
  }
}

/** Fade out and remove the boot loader. Safe to call more than once. */
export function bootDone(): void {
  try {
    loader()?.done();
  } catch {
    /* loader gone — ignore */
  }
}
