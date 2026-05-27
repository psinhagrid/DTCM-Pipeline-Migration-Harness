import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Badge } from "@/components/AppShell";
import { useEffect, useLayoutEffect, useRef, useState, useMemo } from "react";
import { TOKEN_COLORS, tokenizeLine } from "@/lib/highlight";
import {
  Play, Pause, Trash2, Cpu, List, ChevronDown, ChevronRight,
  Brain, Zap, CheckCircle2, XCircle, AlertTriangle, Clock,
  Layers, ArrowRight, Terminal, Activity, GitBranch, Wrench,
} from "lucide-react";
import { onReset } from "@/lib/reset-store";
import { marked } from "marked";
import eventsStore, { type AgentEvent } from "@/lib/events-store";

marked.setOptions({ breaks: true, gfm: true });

export const Route = createFileRoute("/orchestration")({ component: OrchestrationConsole });

// ── Phase detection ───────────────────────────────────────────────────────────
const PHASE_TOOLS: Record<string, string[]> = {
  ASSESS:    ["scan-repo","parse-hql","lineage-extract","classify-complexity","neo4j-write","query-graph"],
  CONVERT:   ["transform-hql","generate-dag"],
  RECONCILE: ["validate-pyspark","analyze-file","workflow-parity","runtime-validation","compile-report"],
  DEPLOY:    ["validate-artifacts","run-smoke-tests","compute-governance","generate-cicd","write-manifests"],
};

const PHASE_ORDER = ["ASSESS","CONVERT","RECONCILE","DEPLOY"] as const;
type Phase = typeof PHASE_ORDER[number];

const PHASE_META: Record<Phase, { color: string; border: string; bg: string; dot: string; icon: React.ReactNode }> = {
  ASSESS:    { color:"text-sky-400",    border:"border-sky-500/40",    bg:"bg-sky-500/8",    dot:"bg-sky-400",    icon:<GitBranch className="h-3 w-3"/> },
  CONVERT:   { color:"text-violet-400", border:"border-violet-500/40", bg:"bg-violet-500/8", dot:"bg-violet-400", icon:<Zap className="h-3 w-3"/>        },
  RECONCILE: { color:"text-amber-400",  border:"border-amber-500/40",  bg:"bg-amber-500/8",  dot:"bg-amber-400",  icon:<Activity className="h-3 w-3"/>   },
  DEPLOY:    { color:"text-emerald-400",border:"border-emerald-500/40",bg:"bg-emerald-500/8",dot:"bg-emerald-400",icon:<Layers className="h-3 w-3"/>      },
};

function detectPhase(toolName: string): Phase | null {
  for (const [phase, tools] of Object.entries(PHASE_TOOLS)) {
    if (tools.some(t => toolName.toLowerCase().includes(t))) return phase as Phase;
  }
  const lower = toolName.toLowerCase();
  if (lower.includes("scan") || lower.includes("parse") || lower.includes("lineage") || lower.includes("classify")) return "ASSESS";
  if (lower.includes("transform") || lower.includes("dag") || lower.includes("convert")) return "CONVERT";
  if (lower.includes("validate") || lower.includes("reconcile") || lower.includes("parity") || lower.includes("report")) return "RECONCILE";
  if (lower.includes("deploy") || lower.includes("smoke") || lower.includes("govern") || lower.includes("cicd") || lower.includes("manifest")) return "DEPLOY";
  return null;
}

const agentColor: Record<string, string> = {
  supervisor: "text-agent-supervisor",
  rlm_agent:  "text-primary",
};

const agentLabel: Record<string, string> = {
  supervisor: "SUPERVISOR",
  rlm_agent:  "RLM",
};

function isNarration(msg: string): boolean {
  if (!msg) return false;
  const t = msg.trim();
  if (/^[✓⚠✗–→←]/.test(t)) return false;
  if (t.length < 30) return false;
  return /^[A-Z]/.test(t) && t.includes(" ");
}

function formatTs(iso?: string): string {
  if (!iso) return new Date().toTimeString().slice(0, 8);
  try { return new Date(iso).toTimeString().slice(0, 8); } catch { return iso.slice(11, 19); }
}

interface PendingInput { situation: string; options: string[]; pipeline: string; }

function ReasoningBlock({ ev }: { ev: AgentEvent }) {
  const [open, setOpen] = useState(false);
  const lines = (ev.code ?? "").split("\n");
  return (
    <div className="my-2 rounded-lg overflow-hidden border border-purple-300/30" style={{background:"oklch(0.14 0.04 290 / 0.18)"}}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-left hover:bg-purple-500/10 transition-colors group"
      >
        <Brain className="h-3.5 w-3.5 text-purple-400 shrink-0" />
        <span className="text-[10px] font-mono uppercase tracking-widest text-purple-400/60 shrink-0 tabular-nums">
          step {ev.step ?? "?"}
        </span>
        <span className="text-[12px] text-purple-200/80 flex-1 truncate font-medium">{ev.message}</span>
        {ev.code && <span className="text-[10px] font-mono text-purple-400/30 shrink-0 tabular-nums">{lines.length} lines</span>}
        <span className="text-[10px] font-mono text-purple-400/40 shrink-0 ml-2 tabular-nums">{formatTs(ev.timestamp)}</span>
        {open
          ? <ChevronDown  className="h-3 w-3 text-purple-400/50 shrink-0 group-hover:text-purple-400/80 transition-colors" />
          : <ChevronRight className="h-3 w-3 text-purple-400/50 shrink-0 group-hover:text-purple-400/80 transition-colors" />}
      </button>
      {open && ev.code && (
        <div className="border-t border-purple-400/15 overflow-auto max-h-[500px]" style={{background:"oklch(0.10 0.02 270)"}}>
          <pre className="p-3 text-[12px] leading-[1.6] font-mono">
            {lines.map((line, i) => (
              <div key={i} className="flex gap-3 group/ln hover:bg-white/[0.03] rounded px-1">
                <span className="text-purple-900/80 select-none w-8 text-right shrink-0 text-[11px] pt-px tabular-nums">{i + 1}</span>
                <span className="flex-1 whitespace-pre">
                  {tokenizeLine(line, "python").map((tok, j) => (
                    <span key={j} className={TOKEN_COLORS[tok.kind] ?? "text-slate-200"}>{tok.text}</span>
                  ))}
                </span>
              </div>
            ))}
          </pre>
        </div>
      )}
    </div>
  );
}

function ToolPairCard({ callEv, resultEv }: { callEv: AgentEvent; resultEv?: AgentEvent }) {
  const tool    = callEv.tool_name ?? callEv.message.replace("⚙ ", "");
  const isOk    = resultEv ? resultEv.ok !== false : null;
  const summary = resultEv?.summary ?? resultEv?.message?.replace("  ↳ ", "") ?? null;
  const phase   = detectPhase(tool);
  const meta    = phase ? PHASE_META[phase] : null;

  const borderColor = isOk === true ? "border-l-emerald-500/70" : isOk === false ? "border-l-red-500/70" : "border-l-primary/40";
  const bgColor     = isOk === true ? "bg-emerald-500/[0.04]"  : isOk === false ? "bg-red-500/[0.06]"    : "bg-primary/[0.04]";

  return (
    <div className={`my-1 rounded-r-lg border border-border/60 border-l-2 ${borderColor} ${bgColor} overflow-hidden`}>
      <div className="flex items-center gap-2.5 px-3 py-2">
        <Wrench className="h-3 w-3 text-muted-foreground/40 shrink-0" />
        <span className="font-mono font-semibold text-[12px] text-foreground/90 flex-1">{tool}</span>
        {meta && (
          <span className={`text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded border ${meta.color} ${meta.border} ${meta.bg} shrink-0`}>
            {phase}
          </span>
        )}
        {isOk === null  && <span className="text-[10px] font-mono text-muted-foreground/40 shrink-0">calling…</span>}
        {isOk === true  && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />}
        {isOk === false && <XCircle      className="h-3.5 w-3.5 text-red-500 shrink-0" />}
        <span className="text-[10px] font-mono text-muted-foreground/40 shrink-0 tabular-nums">{formatTs(callEv.timestamp)}</span>
      </div>
      {summary && (
        <div className="flex items-start gap-2.5 px-3 pb-2 border-t border-border/30">
          <span className="text-[10px] font-mono text-muted-foreground/30 shrink-0 mt-0.5">↳</span>
          <span className={`text-[11px] font-mono leading-relaxed ${isOk === false ? "text-red-400/80" : "text-muted-foreground/70"}`}>
            {summary}
          </span>
        </div>
      )}
    </div>
  );
}

function DelegationDivider({ ev }: { ev: AgentEvent }) {
  const color = agentColor[ev.agent] ?? "text-foreground";
  const label = agentLabel[ev.agent] ?? ev.agent.toUpperCase();
  return (
    <div className="flex items-center gap-3 my-3 px-1">
      <div className="flex items-center gap-2 shrink-0">
        <span className={`h-2 w-2 rounded-full shrink-0 pulse-dot ${
          ev.agent === "supervisor" ? "bg-agent-supervisor" : "bg-primary"
        }`}/>
        <span className={`text-[11px] font-mono font-bold uppercase tracking-widest ${color}`}>{label}</span>
      </div>
      <ArrowRight className="h-3 w-3 text-muted-foreground/30 shrink-0" />
      <span className="text-[13px] text-foreground/80 font-medium truncate flex-1">{ev.target ?? ev.message}</span>
      <div className="h-px flex-1 bg-border/40 min-w-[24px]" />
      <span className="text-[10px] font-mono text-muted-foreground/40 shrink-0 tabular-nums">{formatTs(ev.timestamp)}</span>
    </div>
  );
}


function OrchestrationConsole() {
  const [events,       setEvents]       = useState<AgentEvent[]>([...eventsStore.events]);
  const [connected,    setConnected]    = useState(false);
  const [paused,       setPaused]       = useState(false);
  const [filter,       setFilter]       = useState("all");
  const [verbose,      setVerbose]      = useState(false);
  const [pendingInput, setPendingInput] = useState<PendingInput | null>(null);
  const [chosenMap,    setChosenMap]    = useState<Record<string, string>>({});
  const [startTime,    setStartTime]    = useState<Date | null>(null);
  const [elapsed,      setElapsed]      = useState("00:00");
  const scrollRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    if (!connected || !startTime) return;
    const id = setInterval(() => {
      const secs = Math.floor((Date.now() - startTime.getTime()) / 1000);
      const m = String(Math.floor(secs / 60)).padStart(2, "0");
      const s = String(secs % 60).padStart(2, "0");
      setElapsed(`${m}:${s}`);
    }, 1000);
    return () => clearInterval(id);
  }, [connected, startTime]);

  useEffect(() => onReset(() => {
    eventsStore.events.splice(0, eventsStore.events.length);
    setEvents([]);
    setConnected(false);
    setStartTime(null);
    setElapsed("00:00");
  }), []);

  useEffect(() => {
    const es = new EventSource("/stream");
    es.onopen  = () => { setConnected(true); setStartTime(new Date()); };
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const ev: AgentEvent = JSON.parse(e.data);
        if (ev.type === "user_input_required") {
          setPendingInput({
            situation: (ev as any).situation || ev.message,
            options:   (ev as any).options   || [],
            pipeline:  ev.pipeline || "",
          });
          if (!pausedRef.current) {
            if (eventsStore.events.length >= 500) eventsStore.events.splice(0, eventsStore.events.length - 499);
            eventsStore.events.push(ev);
            setEvents([...eventsStore.events]);
          }
          return;
        }
        if (ev.type === "complete") setPendingInput(null);
        if (pausedRef.current) return;
        if (eventsStore.events.length >= 500) eventsStore.events.splice(0, eventsStore.events.length - 499);
        eventsStore.events.push(ev);
        setEvents([...eventsStore.events]);
      } catch {}
    };
    return () => es.close();
  }, []);

  useEffect(() => {
    if (!paused && scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events, paused]);

  useLayoutEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, []);

  async function handleChoice(choice: number, chosen: string, situation: string) {
    setChosenMap(prev => ({ ...prev, [situation]: chosen }));
    setPendingInput(null);
    await fetch(`/user-input?choice=${choice}&chosen=${encodeURIComponent(chosen)}`, { method: "POST" });
  }

  const agentFilters = ["all", "rlm_agent"];

  const filtered = (filter === "all" ? events : events.filter(e => e.agent === filter))
    .filter(e => verbose || e.type !== "hook");

  const pipelineName = useMemo(() => {
    const d = events.find(e => e.type === "delegation");
    return d?.pipeline ?? d?.target ?? "Migration Run";
  }, [events]);

  const currentPhase = useMemo((): Phase | null => {
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i];
      if (ev.type === "tool_call" || ev.type === "tool_result") {
        const tool = ev.tool_name ?? ev.message.replace("⚙ ","");
        const p    = detectPhase(tool);
        if (p) return p;
      }
    }
    return null;
  }, [events]);

  const isComplete = events.some(e => e.type === "complete");

  const timelineItems = useMemo(() => {
    type Item =
      | { kind: "pair"; callEv: AgentEvent; resultEv?: AgentEvent; index: number }
      | { kind: "event"; ev: AgentEvent; index: number };

    const items: Item[] = [];
    const pendingCalls: Record<string, { ev: AgentEvent; idx: number }> = {};
    const consumed = new Set<number>();

    for (let i = 0; i < filtered.length; i++) {
      const ev = filtered[i];
      if (ev.type === "tool_call") {
        const tool = ev.tool_name ?? ev.message.replace("⚙ ","");
        pendingCalls[tool] = { ev, idx: i };
      } else if (ev.type === "tool_result") {
        const tool  = ev.tool_name ?? "";
        const call  = pendingCalls[tool];
        if (call) {
          consumed.add(call.idx);
          consumed.add(i);
          items.push({ kind: "pair", callEv: call.ev, resultEv: ev, index: call.idx });
          delete pendingCalls[tool];
        } else {
          consumed.add(i);
          items.push({ kind: "pair", callEv: ev, resultEv: ev, index: i });
        }
      }
    }
    for (const [, { ev, idx }] of Object.entries(pendingCalls)) {
      consumed.add(idx);
      items.push({ kind: "pair", callEv: ev, resultEv: undefined, index: idx });
    }
    for (let i = 0; i < filtered.length; i++) {
      if (!consumed.has(i)) items.push({ kind: "event", ev: filtered[i], index: i });
    }
    items.sort((a, b) => a.index - b.index);
    return items;
  }, [filtered]);

  return (
    <AppShell>
      <div className="h-full flex flex-col bg-background overflow-hidden">

        {/* Header */}
        <div className="px-5 py-3 border-b border-border bg-white flex items-center gap-4 shrink-0">
          <div className="flex items-center gap-3">
            <div className={`h-8 w-8 rounded-md border flex items-center justify-center shrink-0 ${connected ? "bg-primary/8 border-primary/30" : "bg-surface-2 border-border"}`}>
              <Terminal className={`h-3.5 w-3.5 ${connected ? "text-primary" : "text-muted-foreground/40"}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-[15px] font-semibold tracking-tight text-foreground leading-none">{pipelineName}</h1>
                {currentPhase && !isComplete && (
                  <span className={`text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded border ${PHASE_META[currentPhase].color} ${PHASE_META[currentPhase].border} ${PHASE_META[currentPhase].bg}`}>
                    {currentPhase}
                  </span>
                )}
                {isComplete && (
                  <span className="text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded border text-emerald-600 border-emerald-500/40 bg-emerald-500/8">
                    COMPLETE
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-[10px] font-mono tabular-nums ${connected ? "text-muted-foreground/60" : "text-muted-foreground/30"}`}>
                  {formatTs()} · {elapsed}
                </span>
              </div>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Badge tone={connected ? "success" : "neutral"}>
              {connected ? <><span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot mr-1"/>LIVE</> : "IDLE"}
            </Badge>
            <button onClick={() => setVerbose(v => !v)}
              className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-md border text-[12px] font-mono transition-colors ${verbose ? "bg-info/10 border-info/30 text-info" : "border-border bg-surface-2 text-muted-foreground hover:text-foreground hover:bg-surface-3"}`}>
              <List className="h-3 w-3" />verbose
            </button>
            <button onClick={() => setPaused(p => !p)}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border bg-surface-2 text-[12px] font-mono hover:bg-surface-3 transition-colors">
              {paused ? <><Play className="h-3 w-3 text-success" />resume</> : <><Pause className="h-3 w-3" />pause</>}
            </button>
            <button onClick={() => { eventsStore.events.splice(0, eventsStore.events.length); setEvents([]); setStartTime(null); setElapsed("00:00"); }}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border bg-surface-2 text-[12px] font-mono hover:bg-surface-3 hover:text-danger transition-colors text-muted-foreground">
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        </div>

        {/* Agent filter bar */}
        <div className="px-5 py-2 border-b border-border bg-surface-2/40 flex items-center gap-1.5 shrink-0 overflow-x-auto">
          {agentFilters.map(a => (
            <button key={a} onClick={() => setFilter(a)}
              className={`px-2.5 py-1 rounded border text-[11px] font-mono transition-colors whitespace-nowrap ${filter === a ? "bg-primary text-white border-primary" : "border-border bg-white text-muted-foreground hover:text-foreground hover:bg-surface-3"}`}>
              {a === "all" ? "all agents" : (agentLabel[a] ?? a).toLowerCase()}
            </button>
          ))}
          <span className="ml-auto text-[10px] font-mono text-muted-foreground/50 tabular-nums shrink-0 pl-2">{filtered.length} events</span>
          {paused && <span className="flex items-center gap-1 text-[10px] font-mono text-warning shrink-0"><span className="h-1.5 w-1.5 rounded-full bg-warning pulse-dot"/>paused</span>}
        </div>

        {/* Main body */}
        <div className="flex-1 flex overflow-hidden min-h-0">

          {/* Event timeline */}
          <div ref={scrollRef} className="flex-1 min-w-0 overflow-y-auto bg-white px-5 py-4">
            {timelineItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-3">
                <div className="h-14 w-14 rounded-xl bg-surface-2 border border-border flex items-center justify-center">
                  <Cpu className="h-6 w-6 text-muted-foreground/30" />
                </div>
                <div>
                  <p className="text-[14px] font-medium text-foreground/50">No events yet</p>
                  <p className="text-[12px] text-muted-foreground/50 mt-0.5 font-mono">Run a pipeline from the Dashboard to begin</p>
                </div>
              </div>
            ) : (
              <div className="space-y-0">
                {timelineItems.map((item, i) => {
                  if (item.kind === "pair") {
                    return <ToolPairCard key={`pair-${i}`} callEv={item.callEv} resultEv={item.resultEv} />;
                  }
                  const ev = item.ev;

                  if (ev.type === "user_input_required") {
                    const opts      = (ev as any).options ?? [];
                    const situation = (ev as any).situation || ev.message;
                    const isActive  = pendingInput?.situation === situation;
                    const chosen    = chosenMap[situation];
                    return (
                      <div key={`ev-${i}`} className="my-3 rounded-lg border border-warning/30 bg-warning/5 overflow-hidden">
                        <div className="flex items-center gap-2.5 px-4 py-2.5 bg-warning/8 border-b border-warning/20">
                          <AlertTriangle className={`h-3.5 w-3.5 shrink-0 ${isActive ? "text-warning" : "text-success"}`} />
                          <span className={`text-[10px] font-mono uppercase tracking-widest font-semibold ${isActive ? "text-warning" : "text-success"}`}>
                            {isActive ? "supervisor · awaiting decision" : "supervisor · input received"}
                          </span>
                          <span className="ml-auto text-[10px] font-mono text-muted-foreground/40 tabular-nums">{formatTs(ev.timestamp)}</span>
                        </div>
                        <div className="px-4 py-3">
                          <p className="text-[13px] text-foreground/85 mb-3 leading-relaxed">{situation}</p>
                          {isActive ? (
                            <div className="space-y-1.5">
                              {opts.map((opt: string, oi: number) => (
                                <button key={oi} onClick={() => handleChoice(oi + 1, opt, situation)}
                                  className={`w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-md border text-[13px] transition-colors ${oi === opts.length - 1 ? "border-danger/30 text-danger hover:bg-danger/8" : oi === 0 ? "border-primary/30 text-primary hover:bg-primary/8" : "border-border text-foreground/70 hover:bg-surface-2"}`}>
                                  <span className="font-mono font-bold text-[11px] w-4 shrink-0 tabular-nums">{oi + 1}.</span>
                                  <span>{opt}</span>
                                </button>
                              ))}
                            </div>
                          ) : (
                            <p className="text-[11px] font-mono text-success flex items-center gap-1.5">
                              <CheckCircle2 className="h-3 w-3" />Chose: <span className="font-semibold">"{chosen}"</span>
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  }

                  if (ev.type === "delegation") return <DelegationDivider key={`ev-${i}`} ev={ev} />;

                  if (ev.type === "complete") {
                    return (
                      <div key={`ev-${i}`} className="my-4 rounded-lg border border-emerald-500/30 bg-emerald-500/6 px-5 py-4 flex items-center gap-3">
                        <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />
                        <p className="text-[13px] font-semibold text-emerald-700 flex-1">{ev.message}</p>
                        <span className="text-[10px] font-mono text-muted-foreground/50 tabular-nums">{formatTs(ev.timestamp)}</span>
                      </div>
                    );
                  }

                  if (ev.type === "reasoning") return null;

                  if (ev.type === "status" && isNarration(ev.message)) {
                    const isSuper = ev.agent === "supervisor";
                    const html    = isSuper ? marked.parse(ev.message) as string : null;
                    return (
                      <div key={`ev-${i}`} className="flex gap-3 py-1.5 px-2 rounded hover:bg-surface-2/30 group my-0.5">
                        <span className="text-muted-foreground/35 font-mono text-[10px] w-[68px] shrink-0 mt-0.5 tabular-nums">{formatTs(ev.timestamp)}</span>
                        <div className="flex-1 min-w-0">
                          <span className={`text-[10px] font-mono uppercase tracking-widest mr-2 ${agentColor[ev.agent] ?? "text-muted-foreground"}`}>
                            {agentLabel[ev.agent] ?? ev.agent}
                          </span>
                          {html ? (
                            <div className="inline prose prose-sm prose-neutral max-w-none text-[13px] leading-relaxed
                              [&_table]:border-collapse [&_table]:text-[12px] [&_table]:font-mono [&_table]:my-1
                              [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-0.5 [&_th]:bg-surface-2 [&_th]:text-left
                              [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-0.5
                              [&_strong]:text-foreground [&_code]:bg-surface-2 [&_code]:px-1 [&_code]:rounded [&_code]:text-[11px]
                              [&_p]:mb-1 [&_p:last-child]:mb-0 [&_ul]:my-1 [&_li]:ml-4"
                              dangerouslySetInnerHTML={{ __html: html }}
                            />
                          ) : (
                            <span className="text-[13px] text-foreground/80 leading-relaxed">{ev.message}</span>
                          )}
                        </div>
                      </div>
                    );
                  }

                  if (ev.type === "artifact" || ev.type === "validation") {
                    return (
                      <div key={`ev-${i}`} className="flex gap-3 py-0.5 px-2 group">
                        <span className="text-muted-foreground/30 font-mono text-[10px] w-[68px] shrink-0 tabular-nums">{formatTs(ev.timestamp)}</span>
                        <span className="text-[12px] text-success flex-1">{ev.message}</span>
                      </div>
                    );
                  }

                  if (ev.type === "hook") {
                    return (
                      <div key={`ev-${i}`} className="flex gap-3 py-0.5 px-2 group opacity-35">
                        <span className="text-muted-foreground/30 font-mono text-[10px] w-[68px] shrink-0 tabular-nums">{formatTs(ev.timestamp)}</span>
                        <span className="text-[10px] font-mono text-warning/70 flex-1">{ev.message}</span>
                      </div>
                    );
                  }

                  return (
                    <div key={`ev-${i}`} className="flex gap-3 py-0.5 px-2 hover:bg-surface-2/20 rounded group">
                      <span className="text-muted-foreground/30 font-mono text-[10px] w-[68px] shrink-0 tabular-nums">{formatTs(ev.timestamp)}</span>
                      <span className={`text-[10px] font-mono uppercase tracking-widest w-[80px] shrink-0 ${agentColor[ev.agent] ?? "text-muted-foreground"}`}>
                        {agentLabel[ev.agent] ?? ev.agent}
                      </span>
                      <span className="text-[12px] text-foreground/65 flex-1 leading-relaxed">{ev.message}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Status bar */}
        <div className="px-5 py-1.5 border-t border-border bg-surface-2/50 flex items-center gap-4 text-[10px] font-mono text-muted-foreground/60 shrink-0">
          <span className={`flex items-center gap-1.5 ${connected ? "text-success" : ""}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-success pulse-dot" : "bg-muted-foreground/40"}`} />
            {connected ? "streaming" : "idle"}
          </span>
          <span className="flex items-center gap-1 tabular-nums">
            <Clock className="h-2.5 w-2.5" />{elapsed}
          </span>
          <span className="tabular-nums">{events.length} total · {filtered.length} shown</span>
          {!verbose && <span className="text-muted-foreground/35">hooks hidden</span>}
          {paused && <span className="text-warning ml-auto flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-warning pulse-dot"/>stream paused</span>}
        </div>
      </div>
    </AppShell>
  );
}
