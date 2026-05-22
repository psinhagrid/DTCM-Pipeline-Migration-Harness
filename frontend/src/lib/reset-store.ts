/**
 * Tiny pub/sub for the global Reset action.
 * Any page can subscribe to be notified when the user hits Reset.
 * No React dependency — plain module-level state so it survives re-renders.
 */

const _listeners: Array<() => void> = [];

export function triggerReset(): void {
  _listeners.forEach((fn) => fn());
}

export function onReset(fn: () => void): () => void {
  _listeners.push(fn);
  return () => {
    const i = _listeners.indexOf(fn);
    if (i >= 0) _listeners.splice(i, 1);
  };
}
