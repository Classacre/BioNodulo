import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en';
import es from './locales/es';

const STORAGE_KEY = 'bionodulo.language';

export const supportedLanguages = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Espanol' },
] as const;

export type SupportedLanguage = typeof supportedLanguages[number]['code'];

function getInitialLanguage(): SupportedLanguage {
  if (typeof localStorage !== 'undefined' && typeof localStorage.getItem === 'function') {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'en' || stored === 'es') return stored;
  }

  if (typeof navigator !== 'undefined') {
    const language = navigator.language.toLowerCase();
    if (language.startsWith('es')) return 'es';
  }

  return 'en';
}

if (!i18n.isInitialized) {
  void i18n
    .use(initReactI18next)
    .init({
      resources: {
        en: { translation: en },
        es: { translation: es },
      },
      lng: getInitialLanguage(),
      fallbackLng: 'en',
      interpolation: {
        escapeValue: false,
      },
      returnEmptyString: false,
    });
}

export function setLanguage(language: SupportedLanguage) {
  try {
    if (typeof localStorage !== 'undefined' && typeof localStorage.setItem === 'function') {
      localStorage.setItem(STORAGE_KEY, language);
    }
  } catch {
    /* ignore */
  }
  return i18n.changeLanguage(language);
}

export default i18n;
