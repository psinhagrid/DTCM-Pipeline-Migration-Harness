import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Badge } from "@/components/AppShell";
import { useEffect, useRef, useState } from "react";
import { Play, Pause, Trash2, Cpu } from "lucide-react";
import { onReset } from "@/lib/reset-store";

export const Route = createFileRoute("/orchestration")({ component: OrchestrationConsole });

// Module-level store — persists across tab switches (component unmount/remount)
let _persistedEvents: Event[] = [];

interface Event {
  type: string;
  agent: string;
  message: string;
  pipeline?: string;
  timestamp?: string;
  target?: string;
  done?: boolean;
}

const agentColor: Record<string, string> = {
  supervisor:      "text-agent-supervisor font-semibold",
  assess_agent:    "text-info",
  convert_agent:   "text-agent-convert",
  reconcile_agent: "text-warning",
  pipeline:        "text-success",
};

const typeColor: Record<string, string> = {
  hook:       "text-agent-hook",
  tool_call:  "text-agent-mcp",
  artifact:   "text-success",
  validation: "text-success",
  delegation: "text-agent-supervisor font-bold",
  complete:   "text-success font-bold",
  error:      "text-danger",
};

function eventColor(ev: Event): string {
  return typeColor[ev.type] || agentColor[ev.agent] || "text-foreground/80";
}

function formatTs(iso?: string): string {
  if (!iso) return new Date().toTimeString().slice(0, 12);
  try { return new Date(iso).toTimeString().slice(0, 12); }
  catch { return iso.slice(11, 23); }
}

function OrchestrationConsole() {
  // Initialise from persisted store so logs survive tab switches
  const [events, setEvents] = useState<Event[]>(_persistedEvents);
  const [connected, setConnected] = useState(false);
  const [paused, setPaused]       = useState(false);
  const [filter, setFilter]       = useState<string>("all");
  const scrollRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  // Listen for global reset
  useEffect(() => onReset(() => {
    _persistedEvents = [];
    setEvents([]);
    setConnected(false);
  }), []);

  useEffect(() => {
    let es: EventSource;

    function connect() {
      es = new EventSource("/stream");
      es.onopen    = () => setConnected(true);
      es.onerror   = () => { setConnected(false); };
      es.onmessage = (e) => {
        if (pausedRef.current) return;
        try {
          const ev: Event = JSON.parse(e.data);
          // Update persisted store AND local state
          _persistedEvents = [..._persistedEvents.slice(-500), ev];
          setEvents([..._persistedEvents]);
        } catch {}
      };
    }

    connect();
    return () => es?.close();
  }, []);

  useEffect(() => {
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, paused]);

  const agentFilters = ["all", "supervisor", "assess_agent", "convert_agent", "reconcile_agent"];
  const filtered = filter === "all" ? events : events.filter((e) => e.agent === filter);

  return (
    <AppShell>
      <div className="h-full flex flex-col bg-background">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4">
          <div>
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Live Orchestration</div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5">
              Supervisor Stream <span className={`ml-2 text-[15px] ${connected ? "text-success" : "text-danger"}`}>
                {connected ? "● connected" : "○ waiting"}
              </span>
            </h1>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Badge tone={connected ? "success" : "neutral"}>{connected ? "SSE LIVE" : "IDLE"}</Badge>
            <button
              onClick={() => setPaused((p) => !p)}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-lg border border-border bg-surface-2 text-[14px] hover:bg-surface-3 transition"
            >
              {paused ? <><Play className="h-4 w-4" /> Resume</> : <><Pause className="h-4 w-4" /> Pause</>}
            </button>
            <button
              onClick={() => { _persistedEvents = []; setEvents([]); }}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-lg border border-border bg-surface-2 text-[14px] hover:bg-surface-3 transition"
            >
              <Trash2 className="h-4 w-4" /> Clear
            </button>
          </div>
        </div>

        {/* Agent filter bar */}
        <div className="px-6 py-2 border-b border-border bg-surface-2/50 flex items-center gap-2 text-[13px] font-mono">
          <span className="text-muted-foreground mr-1">Filter:</span>
          {agentFilters.map((a) => (
            <button
              key={a}
              onClick={() => setFilter(a)}
              className={`px-3 py-1 rounded-md border transition ${
                filter === a
                  ? "bg-primary text-white border-primary"
                  : "border-border bg-white text-muted-foreground hover:text-foreground"
              }`}
            >
              {a}
            </button>
          ))}
          <span className="ml-auto text-muted-foreground">{filtered.length} events</span>
        </div>

        {/* Event stream */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto bg-white px-6 py-4 font-mono">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
              <Cpu className="h-10 w-10 mb-4 opacity-30" />
              <p className="text-[16px]">No events yet</p>
              <p className="text-[14px] mt-1">Run a pipeline from the Dashboard to see live orchestration events here</p>
            </div>
          ) : (
            filtered.map((ev, i) => (
              <div key={i} className="flex gap-4 py-0.5 hover:bg-surface-2/40 rounded px-1 group">
                <span className="text-muted-foreground/60 select-none w-[110px] shrink-0 text-[13px]">
                  {formatTs(ev.timestamp)}
                </span>
                <span className={`w-[130px] shrink-0 text-[13px] uppercase tracking-wide ${agentColor[ev.agent] || "text-foreground"}`}>
                  [{ev.agent}]
                </span>
                <span className={`text-[14px] leading-relaxed flex-1 ${eventColor(ev)}`}>
                  {ev.type === "delegation" && ev.target ? (
                    <><span className="text-muted-foreground">→ </span><span className="font-semibold">{ev.target}</span>  {ev.message}</>
                  ) : ev.message}
                  {ev.pipeline && (
                    <span className="ml-3 text-[12px] text-muted-foreground font-normal">· {ev.pipeline}</span>
                  )}
                </span>
                <span className={`text-[12px] px-1.5 py-0.5 rounded font-mono ml-1 shrink-0 ${
                  ev.type === "complete" ? "bg-success/10 text-success" :
                  ev.type === "hook"     ? "bg-warning/10 text-warning" :
                  ev.type === "tool_call"? "bg-info/10 text-info" :
                  ev.type === "artifact" ? "bg-success/10 text-success" :
                  ev.type === "validation"? "bg-success/10 text-success" :
                  "bg-surface-2 text-muted-foreground"
                }`}>
                  {ev.type}
                </span>
              </div>
            ))
          )}
        </div>

        {/* Status bar */}
        <div className="px-6 py-2 border-t border-border bg-surface-2/60 flex items-center gap-4 text-[13px] font-mono text-muted-foreground">
          <span className={`flex items-center gap-2 ${connected ? "text-success" : "text-muted-foreground"}`}>
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-success pulse-dot" : "bg-muted-foreground"}`} />
            {connected ? "streaming" : "idle"}
          </span>
          <span>events: {events.length}</span>
          <span>filter: {filter}</span>
          {paused && <span className="text-warning">● paused</span>}
        </div>
      </div>
    </AppShell>
  );
}
