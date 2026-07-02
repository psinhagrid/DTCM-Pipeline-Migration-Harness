import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, Panel, Badge } from "@/components/AppShell";
import { useEffect, useRef, useState } from "react";
import { Play, RefreshCw, RotateCcw, ArrowRight } from "lucide-react";
import { triggerReset } from "@/lib/reset-store";
import eventsStore from "@/lib/events-store";

export const Route = createFileRoute("/")({ component: Dashboard });

function Dashboard() {
  const [pipelines,   setPipelines]   = useState<string[]>([]);
  const [results,     setResults]     = useState<Record<string, any>>({});
  const [running,     setRunning]     = useState<Set<string>>(() => {
    try {
      const s = sessionStorage.getItem("rlm_running");
      return s ? new Set(JSON.parse(s)) : new Set();
    } catch { return new Set(); }
  });
  const [runningAll,  setRunningAll]  = useState(false);
  const [liveEvent,   setLiveEvent]   = useState<{ tool: string; description: string } | null>(null);
  const [allProgress, setAllProgress] = useState<string>("");
  const liveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Restore running state from server on mount ─────────────────────────────
  useEffect(() => {
    fetch("/pipelines")
      .then((r) => r.json())
      .then(({ pipelines: pl }) => {
        setPipelines(pl);
        pl.forEach((p: string) =>
          fetch(`/result/${p}`)
            .then((r) => r.ok ? r.json() : null)
            .then((d) => d && setResults((prev) => ({ ...prev, [p]: d })))
        );
      });

    fetch("/status")
      .then((r) => r.json())
      .then(({ running: r }) => {
        setRunning(new Set(r ?? [])); // always apply — server is authoritative
      });
  }, []);

  // ── SSE: listen for live tool calls ───────────────────────────────────────
  useEffect(() => {
    const es = new EventSource("/stream");

    es.onmessage = (e) => {
      let ev: any;
      try { ev = JSON.parse(e.data); } catch { return; }

      // Buffer all events so Logs page has them when user navigates there
      if (eventsStore.events.length < 500) eventsStore.events.push(ev);

      if (ev.type === "tool_call" && ev.tool_name) {
        setLiveEvent({ tool: ev.tool_name, description: ev.description || "" });
        if (liveTimer.current) clearTimeout(liveTimer.current);
        liveTimer.current = setTimeout(() => setLiveEvent(null), 20_000);
      }

      if (ev.type === "complete") {
        setLiveEvent(null);
        if (liveTimer.current) clearTimeout(liveTimer.current);
        // Refresh status + results
        fetch("/status").then((r) => r.json()).then(({ running: r }) =>
          setRunning(new Set(r ?? []))
        );
        setPipelines((pl) => {
          pl.forEach((p) =>
            fetch(`/result/${p}`).then((r) => r.ok ? r.json() : null)
              .then((d) => d && setResults((prev) => ({ ...prev, [p]: d })))
          );
          return pl;
        });
      }
    };

    return () => { es.close(); if (liveTimer.current) clearTimeout(liveTimer.current); };
  }, []);

  // ── Persist running state to sessionStorage for instant restore on nav ───────
  useEffect(() => {
    sessionStorage.setItem("rlm_running", JSON.stringify([...running]));
  }, [running]);

  // ── Poll running state every 5s — always active so page nav restores state ──
  useEffect(() => {
    const id = setInterval(() => {
      fetch("/status").then((r) => r.json()).then(({ running: r }) => {
        const next = new Set<string>(r ?? []);
        setRunning((prev) => {
          for (const p of prev) {
            if (!next.has(p)) {
              fetch(`/result/${p}`).then((r) => r.ok ? r.json() : null)
                .then((d) => d && setResults((prev2) => ({ ...prev2, [p]: d })));
            }
          }
          return next;
        });
      });
    }, 5_000);
    return () => clearInterval(id);
  }, []);

  async function refresh() {
    await fetch("/reset", { method: "POST" });
    setResults({});
    setRunning(new Set());
    triggerReset();
  }

  async function runPipeline(pipeline: string) {
    // Clear previous run's events so Logs page shows "Generating code…" fresh
    eventsStore.events.splice(0, eventsStore.events.length);
    triggerReset();
    setRunning((prev) => new Set([...prev, pipeline]));
    await fetch(`/run?pipeline=${encodeURIComponent(pipeline)}`, { method: "POST" });
  }

  async function runAllInOrder() {
    if (!pipelines.length || runningAll) return;
    setRunningAll(true);

    let waveGroups: string[][] = [pipelines];
    try {
      const graph = await fetch("/graph").then((r) => r.json());
      const gPipelines: { name: string; depends_on: string[] }[] = graph.pipelines ?? [];
      if (gPipelines.length > 0) {
        const tiers = new Map<string, number>();
        const nameSet = new Set(gPipelines.map((p: any) => p.name));
        for (const p of gPipelines) {
          if (p.depends_on.filter((d: string) => nameSet.has(d)).length === 0) tiers.set(p.name, 0);
        }
        let changed = true;
        while (changed) {
          changed = false;
          for (const p of gPipelines) {
            if (tiers.has(p.name)) continue;
            const deps = p.depends_on.filter((d: string) => nameSet.has(d));
            if (deps.every((d: string) => tiers.has(d))) {
              tiers.set(p.name, Math.max(...deps.map((d: string) => tiers.get(d)!)) + 1);
              changed = true;
            }
          }
        }
        for (const p of gPipelines) { if (!tiers.has(p.name)) tiers.set(p.name, 0); }
        const maxTier = Math.max(...[...tiers.values()]);
        waveGroups = Array.from({ length: maxTier + 1 }, (_, i) =>
          [...tiers.entries()].filter(([, t]) => t === i).map(([n]) => n).filter(n => pipelines.includes(n))
        ).filter(g => g.length > 0);
      }
    } catch { /* use fallback */ }

    for (let wi = 0; wi < waveGroups.length; wi++) {
      const wave = waveGroups[wi];
      setAllProgress(`Wave ${wi + 1}/${waveGroups.length}: ${wave.join(", ")}`);
      await Promise.all(wave.map((p) => runPipeline(p)));
    }

    setRunningAll(false);
    setAllProgress("");
  }

  const anyRunning = running.size > 0 || runningAll;

  return (
    <AppShell>
      <div className="h-full overflow-y-auto bg-background p-8 space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Operations Dashboard</div>
            <h1 className="text-3xl font-semibold tracking-tight mt-2">HiveQL → PySpark Migration</h1>
            <p className="text-[16px] text-muted-foreground mt-1">Multi-agent orchestration · {pipelines.length} pipeline{pipelines.length !== 1 ? "s" : ""} available</p>
          </div>
          <button
            onClick={refresh}
            className="inline-flex items-center gap-2 h-10 px-5 rounded-lg border border-border bg-white text-[14px] text-muted-foreground hover:text-foreground hover:bg-surface-2 transition shadow-sm"
            title="Clear all results"
          >
            <RotateCcw className="h-4 w-4" /> Reset
          </button>
        </div>

        {/* Live activity banner */}
        {liveEvent && (
          <div className="flex items-center gap-3 px-5 py-3 rounded-xl border border-blue-200 bg-blue-50 text-[14px]">
            <RefreshCw className="h-4 w-4 text-blue-500 animate-spin flex-shrink-0" />
            <span className="font-mono font-semibold text-blue-700">{liveEvent.tool}</span>
            {liveEvent.description && (
              <span className="text-blue-500">— {liveEvent.description}</span>
            )}
            <Link
              to="/orchestration"
              className="ml-auto flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium"
            >
              Live view <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        )}

        {/* Pipeline list */}
        <Panel eyebrow="Pipelines" title="Available for migration">
          {/* Toolbar */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface-2/40">
            <span className="text-[13px] text-muted-foreground font-mono">
              {runningAll && allProgress
                ? <><RefreshCw className="inline h-3.5 w-3.5 animate-spin mr-1.5 text-primary" />{allProgress}</>
                : `${pipelines.length} pipeline${pipelines.length !== 1 ? "s" : ""}`}
            </span>
            <button
              onClick={runAllInOrder}
              disabled={anyRunning}
              className={`inline-flex items-center gap-2 h-8 px-4 rounded-md text-[13px] font-medium transition ${
                runningAll
                  ? "bg-primary/10 text-primary border border-primary/30 cursor-not-allowed"
                  : anyRunning
                  ? "bg-gray-100 text-gray-400 border border-border cursor-not-allowed"
                  : "bg-primary text-white hover:bg-primary/90"
              }`}
            >
              {runningAll
                ? <><RefreshCw className="h-3.5 w-3.5 animate-spin" /> Running…</>
                : <><Play className="h-3.5 w-3.5" /> Run All</>}
            </button>
          </div>

          {pipelines.length === 0 ? (
            <div className="p-8 text-center text-[15px] text-muted-foreground">
              No pipelines found — add folders to <code className="bg-surface-2 px-1.5 py-0.5 rounded text-[14px]">pipelines/</code>
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {pipelines.map((p) => {
                const isRunning = running.has(p);
                const result    = results[p];
                return (
                  <li key={p} className={`flex items-center gap-6 px-6 py-5 transition-colors ${
                    isRunning ? "bg-blue-50 border-l-4 border-blue-400" : "hover:bg-surface-2/50"
                  }`}>
                    {/* Name + status line */}
                    <div className="flex-1 min-w-0">
                      <div className="text-[16px] font-semibold tracking-tight">{p}</div>
                      {isRunning ? (
                        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                          <RefreshCw className="h-3.5 w-3.5 text-blue-500 animate-spin flex-shrink-0" />
                          {liveEvent
                            ? <>
                                <span className="text-[13px] text-blue-700 font-mono font-semibold">{liveEvent.tool}</span>
                                {liveEvent.description && <span className="text-[13px] text-blue-500">— {liveEvent.description}</span>}
                              </>
                            : <span className="text-[13px] text-blue-600 font-mono">Initialising agent…</span>
                          }
                        </div>
                      ) : result ? (
                        <div className="text-[14px] text-muted-foreground mt-1 font-mono">
                          complexity: {result.complexity} · tables: {result.tables} · udfs: {result.udfs} · effort: {result.estimated_effort}
                        </div>
                      ) : (
                        <div className="text-[14px] text-muted-foreground mt-1">Ready to run</div>
                      )}
                    </div>

                    {/* Status badge */}
                    <div className="flex items-center gap-2">
                      {isRunning ? (
                        <Badge tone="info">RUNNING</Badge>
                      ) : result ? (
                        <>
                          <Badge tone="success">assessed</Badge>
                          <Badge tone={result.complexity === "SMALL" ? "success" : result.complexity === "MEDIUM" ? "info" : "warning"}>
                            {result.complexity}
                          </Badge>
                        </>
                      ) : (
                        <Badge tone="neutral">not run</Badge>
                      )}
                    </div>

                    {/* Run button */}
                    <button
                      onClick={() => runPipeline(p)}
                      disabled={anyRunning}
                      className={`inline-flex items-center gap-2 h-10 px-5 rounded-lg text-[14px] font-medium transition ${
                        isRunning
                          ? "bg-blue-100 text-blue-600 border border-blue-300 cursor-not-allowed"
                          : anyRunning
                          ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                          : "bg-primary text-white hover:bg-primary/90"
                      }`}
                    >
                      {isRunning
                        ? <><RefreshCw className="h-4 w-4 animate-spin" /> Running…</>
                        : <><Play className="h-4 w-4" /> Run</>
                      }
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        {/* Quick stats */}
        {Object.keys(results).length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Pipelines available", value: pipelines.length },
              { label: "Assessed",             value: Object.keys(results).length },
              { label: "Total tables",         value: Object.values(results).reduce((s: number, r: any) => s + (r.tables || 0), 0) },
              { label: "Total UDFs detected",  value: Object.values(results).reduce((s: number, r: any) => s + (r.udfs || 0), 0) },
            ].map((stat) => (
              <div key={stat.label} className="rounded-lg border border-border bg-white p-5 shadow-sm">
                <div className="text-[13px] uppercase tracking-wider text-muted-foreground font-mono">{stat.label}</div>
                <div className="text-3xl font-semibold mt-2">{stat.value}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
