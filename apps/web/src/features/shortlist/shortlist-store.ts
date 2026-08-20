"use client";

import { useSyncExternalStore } from "react";

const KEY = "scoutglobe.shortlist";
const MAX = 4;

/**
 * The shortlist lives in the browser.
 *
 * The database has tables for it and they stay empty on purpose: nothing here
 * has accounts, so a server-side list would be one list shared by every
 * visitor — anyone could add to and delete from anyone else's. A list in
 * localStorage is private, needs no login, and is honest about being per-device.
 *
 * The comparison it feeds is stateless and lives in the URL, so a scout can
 * still send someone else exactly what he is looking at.
 */
export interface ShortlistEntry {
  id: number;
  name: string;
}

function read(): ShortlistEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (entry): entry is ShortlistEntry =>
          typeof entry === "object" &&
          entry !== null &&
          typeof (entry as ShortlistEntry).id === "number" &&
          typeof (entry as ShortlistEntry).name === "string",
      )
      .slice(0, MAX);
  } catch {
    // A corrupt entry must not take the page down with it.
    return [];
  }
}

let snapshot: ShortlistEntry[] = [];
let hydrated = false;
const listeners = new Set<() => void>();

function getSnapshot(): ShortlistEntry[] {
  if (!hydrated) {
    snapshot = read();
    hydrated = true;
  }
  return snapshot;
}

/** The server has no localStorage; an empty list is the honest placeholder. */
function getServerSnapshot(): ShortlistEntry[] {
  return [];
}

function emit(next: ShortlistEntry[]) {
  snapshot = next;
  hydrated = true;
  window.localStorage.setItem(KEY, JSON.stringify(next));
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  // Another tab is the same scout with the same list.
  const onStorage = (event: StorageEvent) => {
    if (event.key === KEY) {
      snapshot = read();
      hydrated = true;
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useShortlist() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export const shortlist = {
  max: MAX,
  /** Add, or drop if already there. At the cap the oldest makes room. */
  toggle(entry: ShortlistEntry) {
    const current = getSnapshot();
    const without = current.filter((item) => item.id !== entry.id);
    if (without.length !== current.length) return emit(without);
    if (current.length >= MAX) return emit([...current.slice(1), entry]);
    return emit([...current, entry]);
  },
  remove(id: number) {
    emit(getSnapshot().filter((item) => item.id !== id));
  },
  clear() {
    emit([]);
  },
};
