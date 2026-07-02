export interface AgentEvent {
  type: string;
  agent: string;
  message: string;
  pipeline?: string;
  timestamp?: string;
  target?: string;
  tool_name?: string;
  description?: string;
  summary?: string;
  ok?: boolean;
  step?: number;
  code?: string;
  done?: boolean;
}

// Module-level singleton — orchestration writes, observability reads.
// Use `.events` array directly; do not replace the reference (push/splice only).
const eventsStore = { events: [] as AgentEvent[] };
export default eventsStore;
