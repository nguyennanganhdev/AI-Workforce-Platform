/**
 * Conversations of one resident (bản trải nghiệm: localStorage, one key per user).
 * Framework-free so every write is a read-modify-write on the latest stored value: two resident tabs
 * never overwrite each other, and the `storage` event keeps other tabs in sync.
 */
import { useSyncExternalStore } from 'react';
import type { Conversation, ConversationMessage } from '../types';

export interface ConversationState {
  conversations: Conversation[];
  messages: ConversationMessage[];
}

const EMPTY: ConversationState = { conversations: [], messages: [] };
const keyFor = (userId: string) => `vhm_resident_v1_${userId}`;

function isState(value: unknown): value is ConversationState {
  return (
    !!value &&
    typeof value === 'object' &&
    Array.isArray((value as ConversationState).conversations) &&
    Array.isArray((value as ConversationState).messages)
  );
}

function read(userId: string): ConversationState {
  try {
    const raw = localStorage.getItem(keyFor(userId));
    if (!raw) return EMPTY;
    const value: unknown = JSON.parse(raw);
    return isState(value) ? value : EMPTY;
  } catch {
    return EMPTY;
  }
}

const caches = new Map<string, ConversationState>();
const listeners = new Map<string, Set<() => void>>();

function emit(userId: string) {
  for (const fn of listeners.get(userId) ?? []) fn();
}

export function getConversationState(userId: string): ConversationState {
  let state = caches.get(userId);
  if (!state) {
    state = read(userId);
    caches.set(userId, state);
  }
  return state;
}

export function subscribeConversations(userId: string, fn: () => void): () => void {
  let set = listeners.get(userId);
  if (!set) {
    set = new Set();
    listeners.set(userId, set);
  }
  set.add(fn);
  const onStorage = (event: StorageEvent) => {
    // key === null: storage was cleared (reset demo).
    if (event.key !== null && event.key !== keyFor(userId)) return;
    caches.set(userId, read(userId));
    fn();
  };
  window.addEventListener('storage', onStorage);
  return () => {
    set.delete(fn);
    window.removeEventListener('storage', onStorage);
  };
}

/** Applies `transform` to the latest stored state. Throws when the browser refuses to store it. */
export function updateConversations(userId: string, transform: (state: ConversationState) => ConversationState): void {
  const next = transform(read(userId));
  try {
    localStorage.setItem(keyFor(userId), JSON.stringify(next));
  } catch {
    throw new Error('Chưa lưu được trên thiết bị. Bộ nhớ có thể đã đầy, hãy bớt ảnh đính kèm rồi thử lại.');
  }
  caches.set(userId, next);
  emit(userId);
}

/** Appends messages whose id is not stored yet, so replaying an event never posts it twice. */
export function appendMessages(state: ConversationState, messages: ConversationMessage[]): ConversationState {
  const known = new Set(state.messages.map((m) => m.id));
  const fresh = messages.filter((m) => !known.has(m.id));
  if (fresh.length === 0) return state;
  const touched = new Map<string, string>();
  for (const m of fresh) {
    const prev = touched.get(m.conversationId);
    if (!prev || m.createdAt > prev) touched.set(m.conversationId, m.createdAt);
  }
  return {
    conversations: state.conversations.map((c) => {
      const at = touched.get(c.id);
      return at && at > c.updatedAt ? { ...c, updatedAt: at } : c;
    }),
    messages: [...state.messages, ...fresh],
  };
}

export function useConversationState(userId: string): ConversationState {
  return useSyncExternalStore(
    (fn) => subscribeConversations(userId, fn),
    () => getConversationState(userId),
    () => EMPTY,
  );
}
