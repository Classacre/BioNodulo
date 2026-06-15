import type { ReactNode } from 'react';
import { useSyncExternalStore } from 'react';
import { getSettingValue } from '../hooks/settings/useSettings';

export type NotificationTone = 'info' | 'success' | 'warning' | 'error' | 'loading';

export interface NotificationAction {
  label: string;
  onClick: (id: string) => void;
  dismiss?: boolean;
}

export interface NotificationOptions {
  id?: string;
  title: ReactNode;
  message?: ReactNode;
  tone?: NotificationTone;
  duration?: number;
  progress?: number | null;
  dismissible?: boolean;
  actions?: NotificationAction[];
}

export interface NotificationRecord extends Required<Pick<NotificationOptions, 'id' | 'tone' | 'dismissible'>> {
  title: ReactNode;
  message?: ReactNode;
  duration: number;
  progress: number | null;
  actions: NotificationAction[];
  createdAt: number;
  expiresAt: number | null;
}

const DEFAULT_DURATION = 5000;
const listeners = new Set<() => void>();
const timers = new Map<string, number>();
let notifications: NotificationRecord[] = [];

function emit() {
  listeners.forEach(listener => listener());
}

function makeId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getDuration(options: NotificationOptions) {
  if (typeof options.duration === 'number') return Math.max(0, options.duration);
  if (options.tone === 'loading') return 0;
  const configured = Number(getSettingValue('bionodulo.notifications.toastDuration', DEFAULT_DURATION));
  return Number.isFinite(configured) && configured > 0 ? configured : DEFAULT_DURATION;
}

function scheduleDismiss(notification: NotificationRecord) {
  const existing = timers.get(notification.id);
  if (existing) window.clearTimeout(existing);
  timers.delete(notification.id);

  if (!notification.duration) return;
  const timeout = window.setTimeout(() => dismissNotification(notification.id), notification.duration);
  timers.set(notification.id, timeout);
}

export function notify(input: string | NotificationOptions): string {
  const options: NotificationOptions = typeof input === 'string' ? { title: input } : input;
  const now = Date.now();
  const duration = getDuration(options);
  const notification: NotificationRecord = {
    id: options.id ?? makeId(),
    title: options.title,
    message: options.message,
    tone: options.tone ?? 'info',
    duration,
    progress: typeof options.progress === 'number' ? options.progress : null,
    dismissible: options.dismissible ?? true,
    actions: options.actions ?? [],
    createdAt: now,
    expiresAt: duration > 0 ? now + duration : null,
  };

  const index = notifications.findIndex(item => item.id === notification.id);
  if (index >= 0) {
    notifications = notifications.map(item => item.id === notification.id ? notification : item);
  } else {
    notifications = [notification, ...notifications];
  }

  scheduleDismiss(notification);
  emit();
  return notification.id;
}

export function updateNotification(id: string, patch: Partial<Omit<NotificationOptions, 'id'>>): void {
  const index = notifications.findIndex(item => item.id === id);
  if (index < 0) return;

  const previous = notifications[index];
  const duration = typeof patch.duration === 'number' ? Math.max(0, patch.duration) : previous.duration;
  const now = Date.now();
  const next: NotificationRecord = {
    ...previous,
    ...patch,
    id,
    tone: patch.tone ?? previous.tone,
    duration,
    progress: typeof patch.progress === 'number' ? patch.progress : patch.progress === null ? null : previous.progress,
    dismissible: patch.dismissible ?? previous.dismissible,
    actions: patch.actions ?? previous.actions,
    expiresAt: typeof patch.duration === 'number' ? (duration > 0 ? now + duration : null) : previous.expiresAt,
  };

  notifications = notifications.map(item => item.id === id ? next : item);
  if (typeof patch.duration === 'number') scheduleDismiss(next);
  emit();
}

export function setNotificationProgress(id: string, progress: number | null): void {
  updateNotification(id, { progress });
}

export function dismissNotification(id: string): void {
  const index = notifications.findIndex(item => item.id === id);
  if (index < 0) return;

  const timer = timers.get(id);
  if (timer) window.clearTimeout(timer);
  timers.delete(id);
  notifications = notifications.filter(item => item.id !== id);
  emit();
}

export function dismissAllNotifications(): void {
  timers.forEach(timer => window.clearTimeout(timer));
  timers.clear();
  notifications = [];
  emit();
}

export function subscribeNotifications(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getNotificationsSnapshot(): NotificationRecord[] {
  return notifications;
}

export function useNotifications(): NotificationRecord[] {
  return useSyncExternalStore(subscribeNotifications, getNotificationsSnapshot, getNotificationsSnapshot);
}

export const toast = {
  show: notify,
  info: (title: ReactNode, options: Omit<NotificationOptions, 'title' | 'tone'> = {}) =>
    notify({ ...options, title, tone: 'info' }),
  success: (title: ReactNode, options: Omit<NotificationOptions, 'title' | 'tone'> = {}) =>
    notify({ ...options, title, tone: 'success' }),
  warning: (title: ReactNode, options: Omit<NotificationOptions, 'title' | 'tone'> = {}) =>
    notify({ ...options, title, tone: 'warning' }),
  error: (title: ReactNode, options: Omit<NotificationOptions, 'title' | 'tone'> = {}) =>
    notify({ ...options, title, tone: 'error', duration: options.duration ?? 8000 }),
  loading: (title: ReactNode, options: Omit<NotificationOptions, 'title' | 'tone' | 'duration'> = {}) =>
    notify({ ...options, title, tone: 'loading', duration: 0, progress: options.progress ?? 0 }),
  update: updateNotification,
  progress: setNotificationProgress,
  dismiss: dismissNotification,
  dismissAll: dismissAllNotifications,
};
