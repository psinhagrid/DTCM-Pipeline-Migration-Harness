import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Badge } from "@/components/AppShell";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Play, Pause, Trash2, Cpu, List } from "lucide-react";
import { onReset } from "@/lib/reset-store";
import { marked } from "marked";

marked.setOptions({ breaks: true, gfm: true });

export const Route = createFileRoute("/orchestration")({ component: OrchestrationConsole });

let _persistedEvents: AgentEvent[] = [];

interface AgentEvent {
  type: string;
  agent: string;
  message: string;
  pipeline?: string;
  timestamp?: string;
  target?: string;
  done?: boolean;
}

const agentColor: Record<string, string> = {
  supervisor:         "text-agent-supervisor",
  assess_subagent:    "text-info",
  convert_subagent:   "text-agent-convert",
  reconcile_subagent: "text-warning",
  deploy_subagent:    "text-agent-validate",
};

// Heuristic: is this a Claude narration line or a short system status line?
function isNarration(msg: string): boolean {
  if (!msg) return false;
  const trimmed = msg.trim();
  // System status lines start with ✓ ⚠ ✗ –, or are very short
  if (/^[✓⚠✗–→←]/.test(trimmed)) return false;
  if (trimmed.length < 30) return false;
  // Narration: full sentence, starts with capital letter
  return /^[A-Z]/.test(trimmed) && trimmed.includes(" ");
}

function formatTs(iso?: string): string {
  if (!iso) return new Date().toTimeString().slice(0, 8);
  try { return new Date(iso).toTimeString().slice(0, 8); }
  catch { return iso.slice(11, 19); }
}

interface PendingInput {
  situation: string;
  options: string[];
  pipeline: string;
}

function OrchestrationConsole() {
  const [events,       setEvents]       = useState<AgentEvent[]>(_persistedEvents);
  const [connected,    setConnected]    = useState(false);
  const [paused,       setPaused]       = useState(false);
  const [filter,       setFilter]       = useState("all");
  const [verbose,      setVerbose]      = useState(false);
  const [pendingInput, setPendingInput] = useState<PendingInput | null>(null);
  const [chosenMap,    setChosenMap]    = useState<Record<string, string>>({});
  const scrollRef  = useRef<HTMLDivElement>(null);
  const pausedRef  = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => onReset(() => {
    _persistedEvents = [];
    setEvents([]);
    setConnected(false);
  }), []);

  useEffect(() => {
    const es = new EventSource("/stream");
    es.onopen    = () => setConnected(true);
    es.onerror   = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const ev: AgentEvent = JSON.parse(e.data);
        if (ev.type === "user_input_required") {
          setPendingInput({
            situation: (ev as any).situation || ev.message,
            options:   (ev as any).options   || [],
            pipeline:  ev.pipeline || "",
          });
          // Also add to log stream so it appears inline
          if (!pausedRef.current) {
            _persistedEvents = [..._persistedEvents.slice(-500), ev];
            setEvents([..._persistedEvents]);
          }
          return;
        }
        if (ev.type === "complete") setPendingInput(null);
        if (pausedRef.current) return;
        _persistedEvents = [..._persistedEvents.slice(-500), ev];
        setEvents([..._persistedEvents]);
      } catch {}
    };
    return () => es.close();
  }, []);

  // Scroll to bottom when new events arrive
  useEffect(() => {
    if (!paused && scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events, paused]);

  // Scroll to bottom on mount — restores position after tab switch
  useLayoutEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, []);

  async function handleChoice(choice: number, chosen: string, situation: string) {
    setChosenMap(prev => ({ ...prev, [situation]: chosen }));
    setPendingInput(null);
    await fetch(`/user-input?choice=${choice}&chosen=${encodeURIComponent(chosen)}`, { method: "POST" });
  }

  const agentFilters = ["all", "supervisor", "assess_subagent", "convert_subagent", "reconcile_subagent", "deploy_subagent"];

  const filtered = (filter === "all" ? events : events.filter((e) => e.agent === filter))
    .filter((e) => verbose || (e.type !== "tool_call" && e.type !== "tool_result" && e.type !== "hook"));

  return (
    <AppShell>
      <div className="h-full flex flex-col bg-background overflow-hidden relative">


        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4 shrink-0">
          <div>
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Live Orchestration</div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5">
              Agent Stream
              <span className={`ml-2 text-[14px] font-normal ${connected ? "text-success" : "text-muted-foreground"}`}>
                {connected ? "● live" : "○ waiting"}
              </span>
            </h1>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Badge tone={connected ? "success" : "neutral"}>{connected ? "SSE LIVE" : "IDLE"}</Badge>

            {/* Verbose toggle */}
            <button
              onClick={() => setVerbose((v) => !v)}
              title={verbose ? "Hide tool calls & hooks" : "Show tool calls & hooks"}
              className={`inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border text-[13px] transition ${
                verbose
                  ? "bg-info/10 border-info/40 text-info"
                  : "border-border bg-surface-2 text-muted-foreground hover:text-foreground"
              }`}
            >
              <List className="h-3.5 w-3.5" />
              {verbose ? "Verbose" : "Verbose"}
            </button>

            <button
              onClick={() => setPaused((p) => !p)}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-lg border border-border bg-surface-2 text-[13px] hover:bg-surface-3 transition"
            >
              {paused ? <><Play className="h-3.5 w-3.5" /> Resume</> : <><Pause className="h-3.5 w-3.5" /> Pause</>}
            </button>
            <button
              onClick={() => { _persistedEvents = []; setEvents([]); }}
              className="inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-border bg-surface-2 text-[13px] hover:bg-surface-3 transition"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Agent filter bar */}
        <div className="px-6 py-2 border-b border-border bg-surface-2/50 flex items-center gap-1.5 text-[12px] font-mono shrink-0">
          <span className="text-muted-foreground mr-1">Agent:</span>
          {agentFilters.map((a) => (
            <button key={a} onClick={() => setFilter(a)}
              className={`px-2.5 py-1 rounded border transition ${
                filter === a
                  ? "bg-primary text-white border-primary"
                  : "border-border bg-white text-muted-foreground hover:text-foreground"
              }`}>
              {a === "all" ? "all" : a.replace("_subagent", "")}
            </button>
          ))}
          <span className="ml-auto text-muted-foreground">{filtered.length} events</span>
        </div>

        {/* Event stream */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto bg-white px-5 py-3">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
              <Cpu className="h-10 w-10 mb-4 opacity-30" />
              <p className="text-[15px]">No events yet</p>
              <p className="text-[13px] mt-1">Run a pipeline from the Dashboard</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {filtered.map((ev, i) => {

                // ── User input prompt — inline in log stream ──────────────
                if (ev.type === "user_input_required") {
                  const opts: string[]  = (ev as any).options ?? [];
                  const situation       = (ev as any).situation || ev.message;
                  const isActive        = pendingInput?.situation === situation;
                  const chosen          = chosenMap[situation];
                  return (
                    <div key={i} className="my-3 rounded-lg border border-warning/40 bg-warning/5 overflow-hidden">
                      <div className="flex items-center gap-2 px-4 py-2 border-b border-warning/20 bg-warning/8">
                        <span className={`h-2 w-2 rounded-full shrink-0 ${isActive ? "bg-warning pulse-dot" : "bg-success"}`} />
                        <span className={`text-[11px] font-mono uppercase tracking-wider font-semibold ${isActive ? "text-warning" : "text-success"}`}>
                          {isActive ? "supervisor · waiting for input" : "supervisor · input received"}
                        </span>
                        <span className="ml-auto text-[11px] font-mono text-muted-foreground/60">{formatTs(ev.timestamp)}</span>
                      </div>
                      <div className="px-4 py-3">
                        <p className="text-[13px] text-foreground/90 mb-3 leading-relaxed">{situation}</p>
                        {isActive ? (
                          <div className="space-y-2">
                            {opts.map((opt, oi) => (
                              <button key={oi} onClick={() => handleChoice(oi + 1, opt, situation)}
                                className={`w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-md border text-[13px] transition ${
                                  oi === opts.length - 1
                                    ? "border-danger/40 text-danger hover:bg-danger/10"
                                    : oi === 0
                                    ? "border-primary/40 text-primary hover:bg-primary/10"
                                    : "border-border text-foreground/70 hover:bg-surface-2"
                                }`}>
                                <span className="font-mono font-bold text-[12px] w-4 shrink-0">{oi + 1}.</span>
                                <span>{opt}</span>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[12px] font-mono text-success">
                            ✓ You chose: <span className="font-semibold">"{chosen}"</span>
                          </p>
                        )}
                      </div>
                    </div>
                  );
                }

                // ── Delegation → visual section break ─────────────────────
                if (ev.type === "delegation") {
                  return (
                    <div key={i} className="flex items-center gap-3 my-3 px-3 py-2 rounded-lg bg-surface-2/80 border border-border">
                      <span className={`text-[12px] font-mono font-semibold uppercase tracking-wider ${agentColor[ev.agent] ?? "text-foreground"}`}>
                        {ev.agent}
                      </span>
                      <span className="text-muted-foreground text-[13px]">→</span>
                      <span className="text-[13px] font-semibold text-foreground">{ev.target ?? ev.message}</span>
                      <span className="ml-auto text-[11px] text-muted-foreground/60 font-mono">{formatTs(ev.timestamp)}</span>
                    </div>
                  );
                }

                // ── Complete ──────────────────────────────────────────────
                if (ev.type === "complete") {
                  return (
                    <div key={i} className="flex items-center gap-2 my-2 px-3 py-2 rounded-lg bg-success/8 border border-success/20">
                      <span className="text-success font-semibold text-[13px]">✓ {ev.message}</span>
                      <span className="ml-auto text-[11px] text-muted-foreground/60 font-mono">{formatTs(ev.timestamp)}</span>
                    </div>
                  );
                }

                // ── Agent narration (Claude reasoning text) ───────────────
                if (ev.type === "status" && isNarration(ev.message)) {
                  const isSuper = ev.agent === "supervisor";
                  const html    = isSuper ? marked.parse(ev.message) as string : null;
                  return (
                    <div key={i} className="flex gap-3 py-1.5 px-2 rounded hover:bg-surface-2/30 group">
                      <span className="text-muted-foreground/50 font-mono text-[11px] w-[70px] shrink-0 mt-0.5">{formatTs(ev.timestamp)}</span>
                      <div className="flex-1 min-w-0">
                        <span className={`text-[11px] font-mono uppercase tracking-wider mr-2 ${agentColor[ev.agent] ?? "text-foreground"}`}>
                          {ev.agent?.replace("_subagent", "")}
                        </span>
                        {html ? (
                          <div
                            className="inline prose prose-sm prose-neutral max-w-none text-[13px] leading-relaxed
                              [&_table]:border-collapse [&_table]:text-[12px] [&_table]:font-mono [&_table]:my-1
                              [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-0.5 [&_th]:bg-surface-2 [&_th]:text-left
                              [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-0.5
                              [&_strong]:text-foreground [&_code]:bg-surface-2 [&_code]:px-1 [&_code]:rounded [&_code]:text-[11px]
                              [&_p]:mb-1 [&_p:last-child]:mb-0 [&_ul]:my-1 [&_li]:ml-4"
                            dangerouslySetInnerHTML={{ __html: html }}
                          />
                        ) : (
                          <span className="text-[14px] text-foreground/90 leading-relaxed">{ev.message}</span>
                        )}
                      </div>
                    </div>
                  );
                }

                // ── Artifact / validation ─────────────────────────────────
                if (ev.type === "artifact" || ev.type === "validation") {
                  return (
                    <div key={i} className="flex gap-3 py-0.5 px-2 group">
                      <span className="text-muted-foreground/40 font-mono text-[11px] w-[70px] shrink-0">{formatTs(ev.timestamp)}</span>
                      <span className="text-[13px] text-success flex-1">{ev.message}</span>
                    </div>
                  );
                }

                // ── Tool call (verbose only) ───────────────────────────────
                if (ev.type === "tool_call") {
                  return (
                    <div key={i} className="flex gap-3 py-0.5 px-2 group opacity-60">
                      <span className="text-muted-foreground/40 font-mono text-[11px] w-[70px] shrink-0">{formatTs(ev.timestamp)}</span>
                      <span className="text-[11px] font-mono text-info flex-1">{ev.message}</span>
                    </div>
                  );
                }

                // ── Tool result (verbose only) ────────────────────────────
                if (ev.type === "tool_result") {
                  return (
                    <div key={i} className="flex gap-3 py-0.5 px-2 group opacity-80">
                      <span className="text-muted-foreground/40 font-mono text-[11px] w-[70px] shrink-0">{formatTs(ev.timestamp)}</span>
                      <span className="text-[11px] font-mono text-muted-foreground flex-1">{ev.message}</span>
                    </div>
                  );
                }

                // ── Hook (verbose only) ───────────────────────────────────
                if (ev.type === "hook") {
                  return (
                    <div key={i} className="flex gap-3 py-0.5 px-2 group opacity-40">
                      <span className="text-muted-foreground/40 font-mono text-[11px] w-[70px] shrink-0">{formatTs(ev.timestamp)}</span>
                      <span className="text-[11px] font-mono text-warning/70 flex-1">{ev.message}</span>
                    </div>
                  );
                }

                // ── Default status (short ✓/⚠ system lines) ──────────────
                return (
                  <div key={i} className="flex gap-3 py-0.5 px-2 hover:bg-surface-2/20 rounded group">
                    <span className="text-muted-foreground/40 font-mono text-[11px] w-[70px] shrink-0">{formatTs(ev.timestamp)}</span>
                    <span className={`text-[11px] font-mono uppercase tracking-wider w-[90px] shrink-0 ${agentColor[ev.agent] ?? "text-muted-foreground"}`}>
                      {ev.agent?.replace("_subagent", "")}
                    </span>
                    <span className="text-[13px] text-foreground/70 flex-1">{ev.message}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Status bar */}
        <div className="px-6 py-2 border-t border-border bg-surface-2/60 flex items-center gap-4 text-[12px] font-mono text-muted-foreground shrink-0">
          <span className={`flex items-center gap-1.5 ${connected ? "text-success" : ""}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-success pulse-dot" : "bg-muted-foreground"}`} />
            {connected ? "streaming" : "idle"}
          </span>
          <span>{events.length} total · {filtered.length} shown</span>
          {!verbose && <span className="text-muted-foreground/60">tool calls + results hidden · toggle Verbose to show</span>}
          {paused && <span className="text-warning ml-auto">● paused</span>}
        </div>
      </div>
    </AppShell>
  );
}
