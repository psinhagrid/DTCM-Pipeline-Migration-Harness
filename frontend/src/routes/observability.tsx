import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/AppShell";
import { useEffect, useState, useMemo, useCallback } from "react";
import { TOKEN_COLORS, tokenizeLine } from "@/lib/highlight";
import eventsStore, { type AgentEvent } from "@/lib/events-store";
import {
  Layers, Terminal, ChevronDown, ChevronRight,
  CheckCircle2, XCircle, Brain, Wrench, Activity,
  GitBranch, Zap, RefreshCw,
} from "lucide-react";

export const Route = createFileRoute("/observability")({ component: ObservabilityPage });

// ── Phase config (mirrors orchestration) ─────────────────────────────────────
const PHASE_TOOLS: Record<string, string[]> = {
  ASSESS:    ["scan-repo","parse-hql","lineage-extract","classify-complexity","neo4j-write","query-graph"],
  CONVERT:   ["transform-hql","generate-dag"],
  RECONCILE: ["validate-pyspark","analyze-file","workflow-parity","runtime-validation","compile-report"],
  DEPLOY:    ["validate-artifacts","run-smoke-tests","compute-governance","generate-cicd","write-manifests"],
};
const PHASE_ORDER = ["ASSESS","CONVERT","RECONCILE","DEPLOY"] as const;
type Phase = typeof PHASE_ORDER[number];

const PHASE_META: Record<Phase, { label: string; color: string; border: string; bg: string; dot: string; textBg: string; icon: React.ReactNode }> = {
  ASSESS:    { label:"Assess",    color:"text-sky-600",     border:"border-sky-200",     bg:"bg-sky-50",     dot:"bg-sky-500",     textBg:"bg-sky-100",     icon:<GitBranch className="h-4 w-4"/>   },
  CONVERT:   { label:"Convert",   color:"text-violet-600",  border:"border-violet-200",  bg:"bg-violet-50",  dot:"bg-violet-500",  textBg:"bg-violet-100",  icon:<Zap className="h-4 w-4"/>         },
  RECONCILE: { label:"Reconcile", color:"text-amber-600",   border:"border-amber-200",   bg:"bg-amber-50",   dot:"bg-amber-500",   textBg:"bg-amber-100",   icon:<Activity className="h-4 w-4"/>   },
  DEPLOY:    { label:"Deploy",    color:"text-emerald-600", border:"border-emerald-200", bg:"bg-emerald-50", dot:"bg-emerald-500", textBg:"bg-emerald-100", icon:<Layers className="h-4 w-4"/>     },
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

function formatTs(iso?: string): string {
  if (!iso) return new Date().toTimeString().slice(0, 8);
  try { return new Date(iso).toTimeString().slice(0, 8); } catch { return iso.slice(11, 19); }
}

interface ToolEntry { callEv: AgentEvent; resultEv?: AgentEvent; phase: Phase | null; }

function buildToolStack(events: AgentEvent[]): Record<string, ToolEntry[]> {
  const byPhase: Record<string, ToolEntry[]> = { ASSESS: [], CONVERT: [], RECONCILE: [], DEPLOY: [], OTHER: [] };
  const pending: Record<string, AgentEvent> = {};
  for (const ev of events) {
    if (ev.type === "tool_call") {
      const tool = ev.tool_name ?? ev.message.replace("⚙ ", "");
      pending[tool] = ev;
    } else if (ev.type === "tool_result") {
      const tool   = ev.tool_name ?? "";
      const callEv = pending[tool];
      const phase  = detectPhase(tool);
      const bucket = phase ?? "OTHER";
      if (callEv) delete pending[tool];
      byPhase[bucket].push({ callEv: callEv ?? ev, resultEv: ev, phase });
    }
  }
  for (const [tool, callEv] of Object.entries(pending)) {
    const phase = detectPhase(tool);
    byPhase[phase ?? "OTHER"].push({ callEv, phase });
  }
  return byPhase;
}

// ── Tool entry card ───────────────────────────────────────────────────────────
function ToolCard({ entry }: { entry: ToolEntry }) {
  const tool    = entry.callEv.tool_name ?? entry.callEv.message.replace("⚙ ", "");
  const isOk    = entry.resultEv ? entry.resultEv.ok !== false : null;
  const summary = entry.resultEv?.summary ?? entry.resultEv?.message?.replace("  ↳ ", "") ?? null;
  const phase   = entry.phase;
  const meta    = phase ? PHASE_META[phase] : null;

  return (
    <div className={`rounded-lg border overflow-hidden transition-all ${
      isOk === true  ? "border-emerald-200 bg-emerald-50/50" :
      isOk === false ? "border-red-200 bg-red-50/50" :
      "border-border bg-white"
    }`}>
      <div className="flex items-center gap-3 px-4 py-2.5">
        <Wrench className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />
        <span className="font-mono font-semibold text-[13px] text-foreground flex-1">{tool}</span>
        {meta && (
          <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border font-semibold ${meta.color} ${meta.border} ${meta.textBg}`}>
            {phase}
          </span>
        )}
        {isOk === null  && <span className="text-[10px] font-mono text-muted-foreground/50 animate-pulse">running…</span>}
        {isOk === true  && <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />}
        {isOk === false && <XCircle      className="h-4 w-4 text-red-500 shrink-0" />}
        <span className="text-[10px] font-mono text-muted-foreground/40 tabular-nums">{formatTs(entry.callEv.timestamp)}</span>
      </div>
      {summary && (
        <div className="px-4 pb-2.5 border-t border-border/40 pt-2">
          <p className={`text-[12px] font-mono leading-relaxed ${isOk === false ? "text-red-500" : "text-muted-foreground/70"}`}>
            {summary.length > 120 ? summary.slice(0, 120) + "…" : summary}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Phase section ─────────────────────────────────────────────────────────────
function PhaseSection({ phase, entries }: { phase: Phase | "OTHER"; entries: ToolEntry[] }) {
  const [open, setOpen] = useState(true);
  const meta    = phase !== "OTHER" ? PHASE_META[phase as Phase] : null;
  const okCount  = entries.filter(e => e.resultEv && e.resultEv.ok !== false).length;
  const errCount = entries.filter(e => e.resultEv?.ok === false).length;
  const pending  = entries.filter(e => !e.resultEv).length;

  return (
    <div className="mb-4">
      <button
        onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border font-medium transition-all text-left ${
          meta ? `${meta.bg} ${meta.border} ${meta.color}` : "bg-surface-2 border-border text-foreground/70"
        }`}
      >
        <span className="flex items-center gap-2 shrink-0">
          {meta?.icon ?? <Wrench className="h-4 w-4" />}
          <span className="text-[13px] font-semibold uppercase tracking-wider">
            {meta?.label ?? "Other"}
          </span>
        </span>
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-[11px] font-mono opacity-60 tabular-nums">{entries.length} tools</span>
          {okCount  > 0 && <span className="text-[11px] font-mono text-emerald-600 font-semibold tabular-nums">✓{okCount}</span>}
          {errCount > 0 && <span className="text-[11px] font-mono text-red-500 font-semibold tabular-nums">✗{errCount}</span>}
          {pending  > 0 && <span className="text-[11px] font-mono text-muted-foreground/50 tabular-nums animate-pulse">…{pending}</span>}
          {open ? <ChevronDown className="h-4 w-4 opacity-60" /> : <ChevronRight className="h-4 w-4 opacity-60" />}
        </div>
      </button>
      {open && (
        <div className="mt-2 space-y-2 pl-2">
          {entries.map((e, i) => <ToolCard key={i} entry={e} />)}
        </div>
      )}
    </div>
  );
}

// ── Code block ────────────────────────────────────────────────────────────────
function CodeBlock({ ev, index }: { ev: AgentEvent; index: number }) {
  const [open, setOpen] = useState(false);
  const lines = (ev.code ?? "").split("\n");

  return (
    <div className="rounded-lg border border-purple-200 overflow-hidden bg-white">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-purple-50/50 transition-colors text-left group"
      >
        <div className="h-6 w-6 rounded-md bg-purple-100 border border-purple-200 flex items-center justify-center shrink-0">
          <Brain className="h-3.5 w-3.5 text-purple-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-purple-400 uppercase tracking-widest">step {ev.step ?? index + 1}</span>
            <span className="text-[10px] font-mono text-muted-foreground/40 tabular-nums">{lines.length} lines</span>
          </div>
          <p className="text-[13px] text-foreground/80 font-medium truncate mt-0.5">{ev.message}</p>
        </div>
        <span className="text-[10px] font-mono text-muted-foreground/40 tabular-nums shrink-0">{formatTs(ev.timestamp)}</span>
        {open
          ? <ChevronDown  className="h-4 w-4 text-purple-400/60 shrink-0 group-hover:text-purple-500 transition-colors" />
          : <ChevronRight className="h-4 w-4 text-purple-400/60 shrink-0 group-hover:text-purple-500 transition-colors" />}
      </button>
      {open && ev.code && (
        <div className="border-t border-purple-100 overflow-auto max-h-[480px]" style={{background:"oklch(0.10 0.02 270)"}}>
          <pre className="p-4 text-[12px] leading-[1.65] font-mono">
            {lines.map((line, i) => (
              <div key={i} className="flex gap-3 hover:bg-white/[0.04] rounded px-1 group/ln">
                <span className="text-purple-900/60 select-none w-8 text-right shrink-0 text-[11px] pt-px tabular-nums">{i + 1}</span>
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

// ── Stat card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, color = "text-foreground" }: { label: string; value: number | string; sub?: string; color?: string }) {
  return (
    <div className="rounded-xl border border-border bg-white px-5 py-4 flex flex-col gap-1 shadow-sm">
      <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className={`text-3xl font-bold tabular-nums tracking-tight ${color}`}>{value}</span>
      {sub && <span className="text-[11px] text-muted-foreground/60 font-mono">{sub}</span>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
function ObservabilityPage() {
  const [events, setEvents] = useState<AgentEvent[]>([...eventsStore.events]);
  const [tick, setTick]     = useState(0);

  // Poll the shared store every 800ms
  useEffect(() => {
    const id = setInterval(() => {
      if (eventsStore.events.length !== events.length) {
        setEvents([...eventsStore.events]);
      }
    }, 800);
    return () => clearInterval(id);
  }, [events.length]);

  const refresh = useCallback(() => setEvents([...eventsStore.events]), []);

  const stack     = useMemo(() => buildToolStack(events), [events]);
  const codeSteps = useMemo(() => events.filter(e => e.type === "reasoning" && e.code), [events]);

  const totalTools  = Object.values(stack).reduce((n, arr) => n + arr.length, 0);
  const successRate = totalTools === 0 ? "—" : Math.round(
    (Object.values(stack).flat().filter(e => e.resultEv?.ok !== false && e.resultEv).length / totalTools) * 100
  ) + "%";
  const activePhasesCount = PHASE_ORDER.filter(p => (stack[p]?.length ?? 0) > 0).length;
  const phases = [...PHASE_ORDER, "OTHER"] as (Phase | "OTHER")[];

  return (
    <AppShell>
      <div className="h-full flex flex-col bg-background overflow-hidden">

        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-white shrink-0 flex items-center gap-4">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">Platform</div>
            <h1 className="text-[18px] font-bold tracking-tight text-foreground leading-tight">Observability</h1>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={refresh}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border bg-surface-2 text-[12px] font-mono hover:bg-surface-3 transition-colors text-muted-foreground"
            >
              <RefreshCw className="h-3 w-3" />refresh
            </button>
          </div>
        </div>

        {/* Stat cards */}
        <div className="px-6 py-4 border-b border-border bg-surface-2/30 grid grid-cols-4 gap-4 shrink-0">
          <StatCard label="Tools Fired"   value={totalTools}         sub="total across all phases" />
          <StatCard label="Success Rate"  value={successRate}        sub="completed without error"  color="text-emerald-600" />
          <StatCard label="Active Phases" value={activePhasesCount}  sub="of 4 pipeline phases"    color="text-primary" />
          <StatCard label="Code Blocks"   value={codeSteps.length}   sub="generated by agent"      color="text-purple-600" />
        </div>

        {/* Body: two columns */}
        <div className="flex-1 flex overflow-hidden min-h-0">

          {/* Left: Tool Stack */}
          <div className="flex-1 min-w-0 overflow-y-auto px-6 py-5 border-r border-border">
            <div className="flex items-center gap-2 mb-4">
              <Layers className="h-4 w-4 text-muted-foreground/60" />
              <h2 className="text-[13px] font-semibold text-foreground tracking-tight">Tool Stack</h2>
              <span className="ml-auto text-[11px] font-mono text-muted-foreground/50 tabular-nums">{totalTools} calls</span>
            </div>

            {totalTools === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center gap-3">
                <div className="h-14 w-14 rounded-2xl bg-surface-2 border border-border flex items-center justify-center">
                  <Layers className="h-6 w-6 text-muted-foreground/25" />
                </div>
                <p className="text-[14px] font-medium text-foreground/40">No tools fired yet</p>
                <p className="text-[12px] text-muted-foreground/40 font-mono">Run a pipeline to see tool calls</p>
              </div>
            ) : (
              phases.map(phase => {
                const entries = stack[phase] ?? [];
                if (entries.length === 0) return null;
                return <PhaseSection key={phase} phase={phase} entries={entries} />;
              })
            )}
          </div>

          {/* Right: Generated Code */}
          <div className="flex-1 min-w-0 overflow-y-auto px-6 py-5">
            <div className="flex items-center gap-2 mb-4">
              <Terminal className="h-4 w-4 text-muted-foreground/60" />
              <h2 className="text-[13px] font-semibold text-foreground tracking-tight">Generated Code</h2>
              <span className="ml-auto text-[11px] font-mono text-muted-foreground/50 tabular-nums">{codeSteps.length} blocks</span>
            </div>

            {codeSteps.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center gap-3">
                <div className="h-14 w-14 rounded-2xl bg-surface-2 border border-border flex items-center justify-center">
                  <Terminal className="h-6 w-6 text-muted-foreground/25" />
                </div>
                <p className="text-[14px] font-medium text-foreground/40">No code generated yet</p>
                <p className="text-[12px] text-muted-foreground/40 font-mono">Code blocks appear as agents run</p>
              </div>
            ) : (
              <div className="space-y-3">
                {codeSteps.map((ev, i) => <CodeBlock key={i} ev={ev} index={i} />)}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
