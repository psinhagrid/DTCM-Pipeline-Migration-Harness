import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel, Badge, StatusDot } from "@/components/AppShell";
import { useEffect, useState } from "react";
import { Play, RefreshCw, RotateCcw } from "lucide-react";
import { triggerReset } from "@/lib/reset-store";

export const Route = createFileRoute("/")({ component: Dashboard });

const PHASES = ["Assessing", "Converting", "Reconciling", "Deploying"];

function Dashboard() {
  const [pipelines, setPipelines] = useState<string[]>([]);
  const [results,   setResults]   = useState<Record<string, any>>({});
  const [running,   setRunning]   = useState<string | null>(null);
  const [phase,     setPhase]     = useState<string>("");
  const [runningAll,  setRunningAll]  = useState(false);
  const [allProgress, setAllProgress] = useState<{ current: string; index: number; total: number } | null>(null);

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
  }, []);

  async function refresh() {
    await fetch("/reset", { method: "POST" });
    setResults({});
    triggerReset();
  }

  async function runPipeline(pipeline: string) {
    setRunning(pipeline);
    setPhase("Starting…");
    await fetch(`/run?pipeline=${encodeURIComponent(pipeline)}`, { method: "POST" });

    let phaseIdx = 0;
    const poll = setInterval(async () => {
      setPhase(PHASES[Math.min(phaseIdx, PHASES.length - 1)] + "…");
      phaseIdx++;

      // Pipeline is done when deployment result exists
      const dep = await fetch(`/deployment/${encodeURIComponent(pipeline)}`)
        .then((r) => r.ok ? r.json() : null).catch(() => null);

      if (dep) {
        const res = await fetch(`/result/${encodeURIComponent(pipeline)}`)
          .then((r) => r.ok ? r.json() : null).catch(() => null);
        if (res) setResults((prev) => ({ ...prev, [pipeline]: res }));
        setRunning(null);
        setPhase("");
        clearInterval(poll);
      }
    }, 8000);

    setTimeout(() => { clearInterval(poll); setRunning(null); setPhase(""); }, 900_000);
  }

  async function runAllInOrder() {
    if (!pipelines.length || runningAll) return;
    setRunningAll(true);

    // Fetch graph to compute wave order
    let waveGroups: string[][] = [pipelines]; // fallback: all in one wave
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
      setAllProgress({ current: `Wave ${wi + 1}/${waveGroups.length}: ${wave.join(", ")}`, index: wi + 1, total: waveGroups.length });

      // Start all pipelines in this wave simultaneously
      await Promise.all(wave.map(async (p) => {
        setRunning(p);
        setPhase("Starting…");
        await fetch(`/run?pipeline=${encodeURIComponent(p)}`, { method: "POST" });

        await new Promise<void>((resolve) => {
          let phaseIdx = 0;
          const poll = setInterval(async () => {
            setPhase(PHASES[Math.min(phaseIdx, PHASES.length - 1)] + "…");
            phaseIdx++;
            const dep = await fetch(`/deployment/${encodeURIComponent(p)}`)
              .then((r) => r.ok ? r.json() : null).catch(() => null);
            if (dep) {
              const res = await fetch(`/result/${encodeURIComponent(p)}`)
                .then((r) => r.ok ? r.json() : null).catch(() => null);
              if (res) setResults((prev) => ({ ...prev, [p]: res }));
              setRunning(null);
              setPhase("");
              clearInterval(poll);
              resolve();
            }
          }, 8000);
          setTimeout(() => { clearInterval(poll); setRunning(null); setPhase(""); resolve(); }, 900_000);
        });
      }));
    }

    setRunningAll(false);
    setAllProgress(null);
  }

  return (
    <AppShell>
      <div className="h-full overflow-y-auto bg-background p-8 space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Operations Dashboard</div>
            <h1 className="text-3xl font-semibold tracking-tight mt-2">Hadoop → MWAA Migration</h1>
            <p className="text-[16px] text-muted-foreground mt-1">DTCM analytics estate · Multi-agent orchestration</p>
          </div>
          <button
            onClick={refresh}
            className="inline-flex items-center gap-2 h-10 px-5 rounded-lg border border-border bg-white text-[14px] text-muted-foreground hover:text-foreground hover:bg-surface-2 transition shadow-sm"
            title="Refresh results from server"
          >
            <RotateCcw className="h-4 w-4" /> Reset
          </button>
        </div>

        {/* Pipeline list */}
        <Panel eyebrow="Pipelines" title="Available for migration">
          {/* Toolbar — bulk action + wave progress */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface-2/40">
            <span className="text-[13px] text-muted-foreground font-mono">
              {runningAll && allProgress
                ? <><RefreshCw className="inline h-3.5 w-3.5 animate-spin mr-1.5 text-primary" />{allProgress.current}</>
                : `${pipelines.length} pipeline${pipelines.length !== 1 ? "s" : ""}`}
            </span>
            <button
              onClick={runAllInOrder}
              disabled={!!running || runningAll}
              className={`inline-flex items-center gap-2 h-8 px-4 rounded-md text-[13px] font-medium transition ${
                runningAll
                  ? "bg-primary/10 text-primary border border-primary/30 cursor-not-allowed"
                  : running
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
                const result = results[p];
                const recon  = null; // loaded separately if needed
                return (
                  <li key={p} className={`flex items-center gap-6 px-6 py-5 transition-colors ${
                    running === p ? "bg-blue-50 border-l-4 border-blue-400" : "hover:bg-surface-2/50"
                  }`}>
                    {/* Name + phase */}
                    <div className="flex-1 min-w-0">
                      <div className="text-[16px] font-semibold tracking-tight">{p}</div>
                      {running === p ? (
                        <div className="flex items-center gap-2 mt-1.5">
                          <RefreshCw className="h-3.5 w-3.5 text-blue-500 animate-spin" />
                          <span className="text-[14px] text-blue-600 font-mono font-medium">{phase}</span>
                          <span className="text-[13px] text-blue-400">· check Logs for live events</span>
                        </div>
                      ) : result ? (
                        <div className="text-[14px] text-muted-foreground mt-1 font-mono">
                          complexity: {result.complexity} · tables: {result.tables} · udfs: {result.udfs} · effort: {result.estimated_effort}
                        </div>
                      ) : (
                        <div className="text-[14px] text-muted-foreground mt-1">Ready to run</div>
                      )}
                    </div>

                    {/* Status badges */}
                    <div className="flex items-center gap-2">
                      {running === p ? (
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
                      disabled={!!running}
                      className={`inline-flex items-center gap-2 h-10 px-5 rounded-lg text-[14px] font-medium transition ${
                        running === p
                          ? "bg-blue-100 text-blue-600 border border-blue-300 cursor-not-allowed"
                          : running
                          ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                          : "bg-primary text-white hover:bg-primary/90"
                      }`}
                    >
                      {running === p
                        ? <><RefreshCw className="h-4 w-4 animate-spin" /> {phase || "Running…"}</>
                        : <><Play className="h-4 w-4" /> Run Pipeline</>
                      }
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        {/* Quick stats if results exist */}
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
