type RunState = { pipeline: string; phase: string; startedAt: number } | null;

let _state: RunState = null;
const _listeners: Array<(s: RunState) => void> = [];

function notify() {
  _listeners.forEach(fn => fn(_state));
}

export function setRunning(pipeline: string, phase: string) {
  _state = { pipeline, phase, startedAt: Date.now() };
  notify();
}

export function updatePhase(phase: string) {
  if (!_state) return;
  _state = { ..._state, phase };
  notify();
}

export function clearRunning() {
  _state = null;
  notify();
}

export function getRunning(): RunState {
  return _state;
}

export function onRunningChange(fn: (s: RunState) => void): () => void {
  _listeners.push(fn);
  fn(_state);
  return () => {
    const i = _listeners.indexOf(fn);
    if (i >= 0) _listeners.splice(i, 1);
  };
}
