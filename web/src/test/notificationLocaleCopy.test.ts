import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

describe('notification and relative time locale copy', () => {
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

  it('returns notification labels and relative time from the Spanish locale', async () => {
    const { default: i18n, setLanguage } = await import('../i18n');

    await setLanguage('es');

    expect(i18n.t('notifications.dismissed')).toBe('Descartada');
    expect(i18n.t('notifications.new')).toBe('Notificacion nueva');
    expect(i18n.t('notifications.clearAll')).toBe('Borrar todas las notificaciones');
    expect(i18n.t('notifications.empty')).toBe('No hay notificaciones');
    expect(i18n.t('common.minutesAgo', { count: 1 })).toBe('hace 1 minuto');
    expect(i18n.t('common.minutesAgo', { count: 3 })).toBe('hace 3 minutos');
    expect(i18n.t('common.hoursAgo', { count: 2 })).toBe('hace 2 horas');
    expect(i18n.t('common.daysAgo', { count: 4 })).toBe('hace 4 dias');
  });
});
