import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Badge } from "@/components/AppShell";
import { useEffect, useState, useRef, useCallback } from "react";
import { Network, GitBranch, Database, Cpu, ChevronRight, AlertCircle, RefreshCw, ListOrdered, Zap, Layers, ChevronDown } from "lucide-react";

export const Route = createFileRoute("/context-graph")({ component: ContextGraph });

// ── Types ─────────────────────────────────────────────────────────────────────

interface WavePipeline {
  name: string;
  complexity: string | null;
  estimated_effort: string | null;
  depends_on: string[];
  blast_radius: number;
  writes: number;
  udfs: number;
}

interface Wave {
  wave: number;
  can_run_parallel: boolean;
  pipelines: WavePipeline[];
}

interface Pipeline {
  name: string;
  complexity: string | null;
  estimated_effort: string | null;
  reads: string[];
  writes: string[];
  udfs: string[];
  depends_on: string[];
  consumed_by: string[];
}

interface FullGraphNode {
  id: string;
  type: "Pipeline" | "Workflow" | "Job" | "Query" | "Table" | "UDF";
  label: string;
  properties: Record<string, unknown>;
}
interface FullGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}
interface FullGraph {
  nodes: FullGraphNode[];
  edges: FullGraphEdge[];
  error?: string | null;
}

// ── Complexity colours ────────────────────────────────────────────────────────

const complexityTone: Record<string, "success" | "info" | "warning" | "danger" | "neutral"> = {
  SMALL: "success", MEDIUM: "info", LARGE: "warning", COMPLEX: "danger",
};

const nodeBg: Record<string, string> = {
  SMALL:   "oklch(0.96 0.03 145)", MEDIUM:  "oklch(0.95 0.03 235)",
  LARGE:   "oklch(0.95 0.06 80)",  COMPLEX: "oklch(0.95 0.05 25)",
};
const nodeBorder: Record<string, string> = {
  SMALL:   "oklch(0.65 0.15 145)", MEDIUM:  "oklch(0.55 0.18 235)",
  LARGE:   "oklch(0.70 0.18 80)",  COMPLEX: "oklch(0.60 0.20 25)",
};

// ── Topology helpers ──────────────────────────────────────────────────────────

function computeTiers(pipelines: Pipeline[]): Map<string, number> {
  const tiers  = new Map<string, number>();
  const nameSet = new Set(pipelines.map((p) => p.name));
  for (const p of pipelines) {
    if (p.depends_on.filter((d) => nameSet.has(d)).length === 0) tiers.set(p.name, 0);
  }
  let changed = true;
  while (changed) {
    changed = false;
    for (const p of pipelines) {
      if (tiers.has(p.name)) continue;
      const deps = p.depends_on.filter((d) => nameSet.has(d));
      if (deps.every((d) => tiers.has(d))) {
        tiers.set(p.name, Math.max(...deps.map((d) => tiers.get(d)!)) + 1);
        changed = true;
      }
    }
  }
  for (const p of pipelines) { if (!tiers.has(p.name)) tiers.set(p.name, 0); }
  return tiers;
}

function computeBlastRadius(pipelines: Pipeline[]): Map<string, number> {
  // BFS from each pipeline to find all transitive consumers
  const consumerMap = new Map<string, string[]>();
  for (const p of pipelines) consumerMap.set(p.name, p.consumed_by);

  const blast = new Map<string, number>();
  for (const p of pipelines) {
    const visited = new Set<string>();
    const queue = [...(consumerMap.get(p.name) ?? [])];
    while (queue.length) {
      const n = queue.shift()!;
      if (visited.has(n)) continue;
      visited.add(n);
      queue.push(...(consumerMap.get(n) ?? []));
    }
    blast.set(p.name, visited.size);
  }
  return blast;
}

// ── Main component ────────────────────────────────────────────────────────────

function ContextGraph() {
  const [tab,              setTab]              = useState<"graph" | "plan">("graph");
  const [graphView,        setGraphView]        = useState<"pipeline" | "hierarchy">("pipeline");
  const [data,             setData]             = useState<{ pipelines: Pipeline[]; error: string | null } | null>(null);
  const [fullGraph,        setFullGraph]        = useState<FullGraph | null>(null);
  const [plan,             setPlan]             = useState<{ waves: Wave[]; total_pipelines: number; error: string | null } | null>(null);
  const [selected,         setSelected]         = useState<Pipeline | null>(null);
  const [loading,          setLoading]          = useState(true);
  const [fullGraphLoading, setFullGraphLoading] = useState(false);
  const [planLoading,      setPlanLoading]      = useState(false);
  const [building,         setBuilding]         = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);

  const fetchGraph = useCallback(() => {
    setLoading(true);
    fetch("/graph")
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => { setData({ pipelines: [], error: "Could not reach backend" }); setLoading(false); });
  }, []);

  const fetchFullGraph = useCallback(() => {
    setFullGraphLoading(true);
    fetch("/full-graph")
      .then((r) => r.json())
      .then((d) => { setFullGraph(d); setFullGraphLoading(false); })
      .catch(() => { setFullGraph({ nodes: [], edges: [], error: "Could not reach backend" }); setFullGraphLoading(false); });
  }, []);

  const fetchPlan = useCallback(() => {
    setPlanLoading(true);
    fetch("/migration-plan")
      .then((r) => r.json())
      .then((d) => { setPlan(d); setPlanLoading(false); })
      .catch(() => { setPlan({ waves: [], total_pipelines: 0, error: "Could not reach backend" }); setPlanLoading(false); });
  }, []);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);
  useEffect(() => { if (tab === "plan" && !plan) fetchPlan(); }, [tab]);
  useEffect(() => { if (graphView === "hierarchy" && !fullGraph) fetchFullGraph(); }, [graphView]);

  async function buildGraph() {
    setBuilding(true);
    await fetch("/build-graph", { method: "POST" }).catch(() => {});
    setBuilding(false);
    fetchGraph();
    setFullGraph(null); // invalidate so hierarchy re-fetches
    setPlan(null);
  }

  const pipelines = data?.pipelines ?? [];
  const tiers     = computeTiers(pipelines);
  const blastMap  = computeBlastRadius(pipelines);
  const maxTier   = pipelines.length ? Math.max(...[...tiers.values()]) : 0;

  const byTier: Pipeline[][] = Array.from({ length: maxTier + 1 }, () => []);
  for (const p of pipelines) byTier[tiers.get(p.name) ?? 0].push(p);

  const NODE_W = 180; const NODE_H = 68;
  const TIER_H = 120; const TIER_PAD = 40;

  const pos = new Map<string, { x: number; y: number }>();
  byTier.forEach((tier, ti) => {
    const totalW = tier.length * NODE_W + (tier.length - 1) * 24;
    const startX = Math.max(0, 600 - totalW / 2);
    tier.forEach((p, pi) => {
      pos.set(p.name, { x: startX + pi * (NODE_W + 24) + NODE_W / 2, y: TIER_PAD + ti * TIER_H + NODE_H / 2 });
    });
  });

  const svgH = TIER_PAD * 2 + (maxTier + 1) * TIER_H;
  const svgW = Math.max(800, ...byTier.map((t) => t.length * (NODE_W + 24)));

  const edges: { from: string; to: string }[] = [];
  for (const p of pipelines) {
    for (const dep of p.depends_on) {
      if (pos.has(dep)) edges.push({ from: dep, to: p.name });
    }
  }

  return (
    <AppShell>
      <div className="h-full flex flex-col bg-background overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4 shrink-0">
          <Network className="h-5 w-5 text-info" />
          <div>
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Neo4j · Lineage</div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5">Pipeline Dependency Graph</h1>
          </div>
          {/* Tab switcher */}
          <div className="flex items-center gap-1 ml-6 border border-border rounded-lg p-0.5 bg-surface-2/50">
            {([["graph", "Dependency Graph", Network], ["plan", "Migration Plan", ListOrdered]] as const).map(([id, label, Icon]) => (
              <button key={id} onClick={() => setTab(id)}
                className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-[13px] transition ${
                  tab === id ? "bg-white shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}>
                <Icon className="h-3.5 w-3.5" />{label}
              </button>
            ))}
          </div>

          {tab === "graph" && (
            <div className="flex items-center gap-1 border border-border rounded-lg p-0.5 bg-surface-2/50">
              {([["pipeline", "Pipeline DAG", Network], ["hierarchy", "Full Hierarchy", Layers]] as const).map(([id, label, Icon]) => (
                <button key={id} onClick={() => setGraphView(id)}
                  className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-[13px] transition ${
                    graphView === id ? "bg-white shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}>
                  <Icon className="h-3.5 w-3.5" />{label}
                </button>
              ))}
            </div>
          )}

          <div className="ml-auto flex items-center gap-2">
            <Badge tone={pipelines.length > 0 ? "success" : "neutral"}>
              {pipelines.length} pipeline{pipelines.length !== 1 ? "s" : ""}
            </Badge>
            <Badge tone="neutral">{edges.length} edges</Badge>

            {/* Build graph — calls tools directly, no LLM */}
            <button
              onClick={buildGraph}
              disabled={building || loading}
              className={`inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border text-[13px] font-medium transition ${
                building
                  ? "border-info/40 bg-info/8 text-info cursor-not-allowed"
                  : "border-border bg-white text-muted-foreground hover:text-foreground hover:bg-surface-2"
              }`}
              title="Scan all pipelines and write to Neo4j (no LLM)"
            >
              <Zap className={`h-3.5 w-3.5 ${building ? "animate-pulse" : ""}`} />
              {building ? "Building…" : "Build Graph"}
            </button>

            {/* Refresh display */}
            <button
              onClick={() => { fetchGraph(); if (tab === "plan") fetchPlan(); }}
              disabled={loading || planLoading || building}
              className="inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-border bg-white text-[13px] text-muted-foreground hover:text-foreground hover:bg-surface-2 transition"
              title="Refresh from Neo4j"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${(loading || planLoading) ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* ── Migration Plan tab ──────────────────────────────────────────── */}
        {tab === "plan" && (
          <div className="flex-1 overflow-y-auto p-6">
            {planLoading && (
              <div className="flex items-center justify-center h-40 text-muted-foreground">
                <Cpu className="h-5 w-5 animate-spin mr-2" /> Loading migration plan…
              </div>
            )}
            {!planLoading && plan?.error && (
              <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground">
                <AlertCircle className="h-8 w-8 text-warning" />
                <p className="text-[14px]">{plan.error} — run pipeline assessments first to populate the graph</p>
              </div>
            )}
            {!planLoading && !plan?.error && (plan?.waves ?? []).length === 0 && (
              <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground h-40">
                <ListOrdered className="h-8 w-8 opacity-30" />
                <p className="text-[14px]">No plan yet — run pipeline assessments to populate the graph</p>
              </div>
            )}
            {!planLoading && (plan?.waves ?? []).length > 0 && (
              <div className="max-w-3xl mx-auto space-y-6">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-[15px] font-semibold text-foreground">
                    {plan!.waves.length} migration wave{plan!.waves.length !== 1 ? "s" : ""} · {plan!.total_pipelines} pipelines
                  </h2>
                  <span className="text-[12px] text-muted-foreground font-mono">ordered by dependency depth · within wave: highest blast radius first</span>
                </div>
                {plan!.waves.map((wave) => (
                  <div key={wave.wave} className="rounded-xl border border-border bg-white overflow-hidden">
                    {/* Wave header */}
                    <div className="flex items-center gap-3 px-5 py-3 bg-surface-2/60 border-b border-border">
                      <div className="h-6 w-6 rounded-full bg-primary/10 flex items-center justify-center text-[12px] font-bold text-primary">
                        {wave.wave + 1}
                      </div>
                      <span className="text-[13px] font-semibold text-foreground">
                        Wave {wave.wave + 1}
                        {wave.wave === 0 ? " — migrate first (no dependencies)" : ""}
                      </span>
                      {wave.can_run_parallel && (
                        <Badge tone="info">run in parallel</Badge>
                      )}
                      <span className="ml-auto text-[12px] text-muted-foreground font-mono">
                        {wave.pipelines.length} pipeline{wave.pipelines.length !== 1 ? "s" : ""}
                      </span>
                    </div>
                    {/* Pipeline rows */}
                    <div className="divide-y divide-border">
                      {wave.pipelines.map((p, i) => (
                        <div key={p.name} className="flex items-center gap-4 px-5 py-3.5 hover:bg-surface-2/30 transition">
                          <span className="text-[11px] text-muted-foreground/50 font-mono w-4 shrink-0">{i + 1}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-[14px] font-semibold text-foreground">{p.name}</div>
                            {p.depends_on.length > 0 && (
                              <div className="text-[12px] text-muted-foreground mt-0.5 font-mono">
                                depends on: {p.depends_on.join(", ")}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            {p.complexity && (
                              <Badge tone={
                                p.complexity === "SMALL" ? "success" :
                                p.complexity === "MEDIUM" ? "info" :
                                p.complexity === "LARGE" ? "warning" : "danger"
                              }>{p.complexity}</Badge>
                            )}
                            {p.estimated_effort && (
                              <span className="text-[12px] text-muted-foreground font-mono">{p.estimated_effort}</span>
                            )}
                            {p.blast_radius > 0 && (
                              <span className="text-[11px] px-2 py-0.5 rounded bg-danger/8 text-danger border border-danger/20 font-mono">
                                blast: {p.blast_radius}
                              </span>
                            )}
                            {p.udfs > 0 && (
                              <span className="text-[11px] px-2 py-0.5 rounded bg-warning/8 text-warning border border-warning/20 font-mono">
                                {p.udfs} UDF{p.udfs > 1 ? "s" : ""}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Dependency Graph tab ─────────────────────────────────────────── */}
        {tab === "graph" && loading && (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <Cpu className="h-5 w-5 animate-spin mr-2" /> Loading graph…
          </div>
        )}

        {tab === "graph" && !loading && data?.error && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
            <AlertCircle className="h-10 w-10 text-warning" />
            <p className="text-[15px] font-medium">{data.error}</p>
            <code className="text-[12px] bg-surface-2 px-3 py-2 rounded font-mono">
              docker run --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/dtcm_local --detach neo4j:5
            </code>
          </div>
        )}

        {tab === "graph" && !loading && !data?.error && pipelines.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 text-muted-foreground">
            <Network className="h-10 w-10 opacity-30" />
            <p className="text-[15px]">Graph is empty</p>
            <p className="text-[13px]">Run pipelines from the Dashboard to populate the lineage graph.</p>
          </div>
        )}

        {/* ── Full Hierarchy view ──────────────────────────────────────────── */}
        {tab === "graph" && graphView === "hierarchy" && (
          <div className="flex-1 overflow-y-auto p-6">
            {fullGraphLoading && (
              <div className="flex items-center justify-center h-40 text-muted-foreground">
                <Cpu className="h-5 w-5 animate-spin mr-2" /> Loading hierarchy…
              </div>
            )}
            {!fullGraphLoading && fullGraph?.error && (
              <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground h-40">
                <AlertCircle className="h-8 w-8 text-warning" />
                <p className="text-[14px]">{fullGraph.error}</p>
              </div>
            )}
            {!fullGraphLoading && !fullGraph?.error && fullGraph && (
              <HierarchyView graph={fullGraph} />
            )}
            {!fullGraphLoading && !fullGraph && (
              <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground h-40">
                <Layers className="h-8 w-8 opacity-30" />
                <p className="text-[14px]">Click Build Graph to populate the hierarchy.</p>
              </div>
            )}
          </div>
        )}

        {tab === "graph" && graphView === "pipeline" && !loading && pipelines.length > 0 && (
          <div className="flex-1 flex overflow-hidden" style={{ display: graphView === "hierarchy" ? "none" : undefined }}>
            {/* DAG canvas */}
            <div className="flex-1 overflow-auto bg-surface-2/30 relative">
              <div className="absolute left-0 top-0 bottom-0 w-16 pointer-events-none">
                {byTier.map((_, ti) => (
                  <div key={ti} className="absolute left-2 text-[11px] font-mono text-muted-foreground/60 uppercase tracking-wider"
                    style={{ top: TIER_PAD + ti * TIER_H }}>T{ti + 1}</div>
                ))}
              </div>

              <svg ref={svgRef} width={svgW} height={svgH} className="min-w-full" style={{ marginLeft: 64 }}>
                <defs>
                  <marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto">
                    <path d="M0,0 L0,6 L8,3 z" fill="oklch(0.60 0.012 260)" />
                  </marker>
                </defs>

                {byTier.map((_, ti) => ti > 0 && (
                  <line key={`sep-${ti}`}
                    x1={0} y1={TIER_PAD + ti * TIER_H - TIER_H / 2}
                    x2={svgW} y2={TIER_PAD + ti * TIER_H - TIER_H / 2}
                    stroke="oklch(0.88 0.004 260)" strokeDasharray="4 4" />
                ))}

                {edges.map((e, i) => {
                  const from = pos.get(e.from); const to = pos.get(e.to);
                  if (!from || !to) return null;
                  const my = (from.y + to.y) / 2;
                  const isActive = selected && (selected.name === e.from || selected.name === e.to);
                  const dimmed   = selected && !isActive;
                  return (
                    <path key={i}
                      d={`M ${from.x} ${from.y + NODE_H / 2} C ${from.x} ${my + 20}, ${to.x} ${my - 20}, ${to.x} ${to.y - NODE_H / 2}`}
                      fill="none" stroke="oklch(0.65 0.012 260)"
                      strokeWidth={isActive ? 2 : 1}
                      strokeOpacity={dimmed ? 0.15 : 0.55}
                      markerEnd="url(#arrow)" />
                  );
                })}

                {pipelines.map((p) => {
                  const { x, y } = pos.get(p.name)!;
                  const cx = p.complexity ?? "UNKNOWN";
                  const isActive = selected?.name === p.name;
                  return (
                    <g key={p.name}
                      transform={`translate(${x - NODE_W / 2}, ${y - NODE_H / 2})`}
                      onClick={() => setSelected(isActive ? null : p)}
                      style={{ cursor: "pointer" }}>
                      <rect width={NODE_W} height={NODE_H} rx={6}
                        fill={nodeBg[cx] ?? "oklch(0.96 0.004 260)"}
                        stroke={isActive ? (nodeBorder[cx] ?? "oklch(0.55 0.012 260)") : "oklch(0.88 0.004 260)"}
                        strokeWidth={isActive ? 2 : 1} />
                      <text x={NODE_W / 2} y={20} textAnchor="middle" fontSize={11}
                        fontFamily="JetBrains Mono, monospace" fill="oklch(0.25 0.015 260)" fontWeight={600}>
                        {p.name.length > 22 ? p.name.slice(0, 21) + "…" : p.name}
                      </text>
                      <text x={NODE_W / 2} y={36} textAnchor="middle" fontSize={10}
                        fontFamily="JetBrains Mono, monospace" fill="oklch(0.55 0.012 260)">
                        {cx} · {p.writes.length}w {p.reads.length}r
                      </text>
                      {p.udfs.length > 0 && (
                        <text x={NODE_W / 2} y={50} textAnchor="middle" fontSize={9}
                          fontFamily="JetBrains Mono, monospace" fill="oklch(0.60 0.12 280)">
                          {p.udfs.length} UDF{p.udfs.length > 1 ? "s" : ""}
                        </text>
                      )}
                      {(blastMap.get(p.name) ?? 0) > 0 && (
                        <text x={NODE_W / 2} y={p.udfs.length > 0 ? 62 : 50} textAnchor="middle" fontSize={9}
                          fontFamily="JetBrains Mono, monospace" fill="oklch(0.55 0.20 25)">
                          blast: {blastMap.get(p.name)} pipeline{(blastMap.get(p.name) ?? 0) > 1 ? "s" : ""}
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            </div>

            {/* Detail panel */}
            {selected && (
              <div className="w-80 shrink-0 border-l border-border bg-white overflow-y-auto">
                <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                  <span className="font-mono text-[13px] font-semibold">{selected.name}</span>
                  <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground text-lg leading-none">×</button>
                </div>
                <div className="px-4 py-3 space-y-4 text-[13px]">
                  <div className="flex items-center gap-2">
                    <Badge tone={complexityTone[selected.complexity ?? ""] ?? "neutral"}>
                      {selected.complexity ?? "unknown"}
                    </Badge>
                    {selected.estimated_effort && (
                      <span className="text-muted-foreground">{selected.estimated_effort}</span>
                    )}
                  </div>

                  {selected.depends_on.length > 0 && (
                    <Section icon={<ChevronRight className="h-3.5 w-3.5 rotate-180 text-info" />} title="Depends on">
                      {selected.depends_on.map((d) => (
                        <Chip key={d} label={d} clickable
                          onClick={() => setSelected(pipelines.find((p) => p.name === d) ?? null)} />
                      ))}
                    </Section>
                  )}

                  {selected.consumed_by.length > 0 && (
                    <Section icon={<ChevronRight className="h-3.5 w-3.5 text-info" />} title="Consumed by">
                      {selected.consumed_by.map((d) => (
                        <Chip key={d} label={d} clickable
                          onClick={() => setSelected(pipelines.find((p) => p.name === d) ?? null)} />
                      ))}
                    </Section>
                  )}

                  {selected.reads.length > 0 && (
                    <Section icon={<Database className="h-3.5 w-3.5 text-muted-foreground" />} title="Reads">
                      {selected.reads.map((t) => <Chip key={t} label={t} />)}
                    </Section>
                  )}

                  {selected.writes.length > 0 && (
                    <Section icon={<Database className="h-3.5 w-3.5 text-success" />} title="Writes">
                      {selected.writes.map((t) => <Chip key={t} label={t} />)}
                    </Section>
                  )}

                  {selected.udfs.length > 0 && (
                    <Section icon={<GitBranch className="h-3.5 w-3.5 text-warning" />} title="UDFs">
                      {selected.udfs.map((u) => <Chip key={u} label={u} />)}
                    </Section>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}

// ── Node type styling ─────────────────────────────────────────────────────────

const nodeTypeColor: Record<string, string> = {
  Pipeline: "text-info border-info/30 bg-info/8",
  Workflow: "text-purple-600 border-purple-300 bg-purple-50",
  Job:      "text-warning border-warning/30 bg-warning/8",
  Query:    "text-teal-600 border-teal-300 bg-teal-50",
  Table:    "text-success border-success/30 bg-success/8",
  UDF:      "text-orange-600 border-orange-300 bg-orange-50",
};

const nodeTypeDot: Record<string, string> = {
  Pipeline: "bg-info",
  Workflow: "bg-purple-500",
  Job:      "bg-warning",
  Query:    "bg-teal-500",
  Table:    "bg-success",
  UDF:      "bg-orange-500",
};

// ── Hierarchy view component ──────────────────────────────────────────────────

function HierarchyView({ graph }: { graph: FullGraph }) {
  const [openPipelines, setOpenPipelines] = useState<Set<string>>(new Set());
  const [openJobs,      setOpenJobs]      = useState<Set<string>>(new Set());
  const [selectedNode,  setSelectedNode]  = useState<FullGraphNode | null>(null);

  function selectNode(n: FullGraphNode, e: React.MouseEvent) {
    e.stopPropagation();
    setSelectedNode((prev) => prev?.id === n.id ? null : n);
  }

  const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));

  // Build parent→children map for CONTAINS / HAS_JOB / HAS_QUERY
  const children = new Map<string, string[]>();
  for (const e of graph.edges) {
    if (["CONTAINS", "HAS_JOB", "HAS_QUERY"].includes(e.type)) {
      if (!children.has(e.source)) children.set(e.source, []);
      children.get(e.source)!.push(e.target);
    }
  }

  // Build Query→{reads, writes} from READS/WRITES edges
  const queryTables = new Map<string, { reads: string[]; writes: string[] }>();
  for (const e of graph.edges) {
    if (e.type === "READS" || e.type === "WRITES") {
      const srcNode = nodeMap.get(e.source);
      if (srcNode?.type === "Query") {
        if (!queryTables.has(e.source)) queryTables.set(e.source, { reads: [], writes: [] });
        const tgt = nodeMap.get(e.target);
        if (tgt) {
          if (e.type === "READS") queryTables.get(e.source)!.reads.push(tgt.label);
          else                    queryTables.get(e.source)!.writes.push(tgt.label);
        }
      }
    }
  }

  // Build Job→dep job labels
  const jobDeps = new Map<string, string[]>();
  for (const e of graph.edges) {
    if (e.type === "DEPENDS_ON") {
      const src = nodeMap.get(e.source);
      const tgt = nodeMap.get(e.target);
      if (src?.type === "Job" && tgt?.type === "Job") {
        if (!jobDeps.has(e.source)) jobDeps.set(e.source, []);
        jobDeps.get(e.source)!.push(tgt.label);
      }
    }
  }

  // Pipeline→UDFs
  const pipelineUdfs = new Map<string, string[]>();
  for (const e of graph.edges) {
    if (e.type === "USES_UDF") {
      const src = nodeMap.get(e.source);
      const tgt = nodeMap.get(e.target);
      if (src?.type === "Pipeline" && tgt?.type === "UDF") {
        if (!pipelineUdfs.has(e.source)) pipelineUdfs.set(e.source, []);
        pipelineUdfs.get(e.source)!.push(tgt.label);
      }
    }
  }

  const pipelines = graph.nodes.filter((n) => n.type === "Pipeline")
    .sort((a, b) => a.label.localeCompare(b.label));

  const totalNodes = graph.nodes.length;
  const totalEdges = graph.edges.length;

  function togglePipeline(id: string) {
    setOpenPipelines((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  }
  function toggleJob(id: string) {
    setOpenJobs((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  }

  return (
    <div className="flex gap-4 items-start">
    {/* Main tree */}
    <div className={`space-y-3 transition-all ${selectedNode ? "flex-1 min-w-0" : "max-w-4xl mx-auto w-full"}`}>
      {/* Summary */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        {(["Pipeline","Workflow","Job","Query","Table","UDF"] as const).map((t) => {
          const count = graph.nodes.filter((n) => n.type === t).length;
          if (!count) return null;
          return (
            <span key={t} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-mono border ${nodeTypeColor[t]}`}>
              <span className={`h-2 w-2 rounded-full ${nodeTypeDot[t]}`} />
              {count} {t}{count !== 1 ? "s" : ""}
            </span>
          );
        })}
        <span className="ml-auto text-[12px] font-mono text-muted-foreground">{totalNodes} nodes · {totalEdges} edges</span>
      </div>

      {pipelines.map((p) => {
        const isOpen = openPipelines.has(p.id);
        const props  = p.properties as Record<string, string>;
        const complexity = props.complexity ?? null;
        const effort     = props.estimated_effort ?? null;
        const wfIds  = children.get(p.id) ?? [];
        const wf     = wfIds.length ? nodeMap.get(wfIds[0]) : null;
        const jobIds = wf ? (children.get(wf.id) ?? []) : [];
        const udfs   = pipelineUdfs.get(p.id) ?? [];

        return (
          <div key={p.id} className="rounded-xl border border-border bg-white overflow-hidden">
            {/* Pipeline header */}
            <button
              className={`w-full flex items-center gap-3 px-5 py-3.5 hover:bg-surface-2/40 transition text-left ${selectedNode?.id === p.id ? "bg-info/5 ring-1 ring-inset ring-info/30" : ""}`}
              onClick={(e) => { togglePipeline(p.id); selectNode(p, e); }}
            >
              <ChevronDown className={`h-4 w-4 text-muted-foreground shrink-0 transition-transform ${isOpen ? "" : "-rotate-90"}`} />
              <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${nodeTypeDot.Pipeline}`} />
              <span className="text-[14px] font-semibold text-foreground font-mono flex-1">{p.label}</span>
              <div className="flex items-center gap-2">
                {complexity && (
                  <Badge tone={complexity === "SMALL" ? "success" : complexity === "MEDIUM" ? "info" : complexity === "LARGE" ? "warning" : "danger"}>
                    {complexity}
                  </Badge>
                )}
                {effort && <span className="text-[12px] text-muted-foreground font-mono">{effort}</span>}
                {udfs.length > 0 && (
                  <span className={`text-[11px] px-2 py-0.5 rounded border font-mono ${nodeTypeColor.UDF}`}>
                    {udfs.length} UDF{udfs.length > 1 ? "s" : ""}
                  </span>
                )}
                <span className="text-[12px] text-muted-foreground font-mono ml-1">
                  {jobIds.length} job{jobIds.length !== 1 ? "s" : ""}
                </span>
              </div>
            </button>

            {isOpen && (
              <div className="border-t border-border">
                {/* Workflow row */}
                {wf && (
                  <div
                    className={`flex items-center gap-2 px-7 py-2 bg-purple-50/60 border-b border-purple-100 cursor-pointer hover:bg-purple-100/60 transition ${selectedNode?.id === wf.id ? "ring-1 ring-inset ring-purple-400" : ""}`}
                    onClick={(e) => selectNode(wf, e)}
                  >
                    <span className={`h-2 w-2 rounded-full shrink-0 ${nodeTypeDot.Workflow}`} />
                    <span className="text-[12px] font-mono text-purple-700">Workflow: {wf.label}</span>
                  </div>
                )}

                {/* Jobs */}
                <div className="divide-y divide-border/60">
                  {jobIds.map((jid) => {
                    const j = nodeMap.get(jid);
                    if (!j) return null;
                    const jobOpen = openJobs.has(jid);
                    const qids    = children.get(jid) ?? [];
                    const deps    = jobDeps.get(jid) ?? [];

                    return (
                      <div key={jid}>
                        {/* Job row */}
                        <button
                          className={`w-full flex items-center gap-2 px-9 py-2.5 hover:bg-surface-2/30 transition text-left ${selectedNode?.id === jid ? "bg-warning/5 ring-1 ring-inset ring-warning/40" : ""}`}
                          onClick={(e) => { toggleJob(jid); selectNode(j, e); }}
                        >
                          <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform ${jobOpen ? "" : "-rotate-90"}`} />
                          <span className={`h-2 w-2 rounded-full shrink-0 ${nodeTypeDot.Job}`} />
                          <span className="text-[13px] font-mono text-warning font-medium flex-1">{j.label}</span>
                          <div className="flex items-center gap-2">
                            {deps.length > 0 && (
                              <span className="text-[11px] font-mono text-muted-foreground">
                                depends on: {deps.join(", ")}
                              </span>
                            )}
                            <span className="text-[11px] font-mono text-muted-foreground">
                              {qids.length} quer{qids.length !== 1 ? "ies" : "y"}
                            </span>
                          </div>
                        </button>

                        {/* Queries */}
                        {jobOpen && qids.map((qid, qi) => {
                          const q = nodeMap.get(qid);
                          if (!q) return null;
                          const tables = queryTables.get(qid) ?? { reads: [], writes: [] };

                          return (
                            <div
                              key={qid}
                              className={`px-14 py-2.5 bg-teal-50/30 border-t border-teal-100/60 cursor-pointer hover:bg-teal-50/60 transition ${selectedNode?.id === qid ? "ring-1 ring-inset ring-teal-400" : ""}`}
                              onClick={(e) => selectNode(q, e)}
                            >
                              <div className="flex items-center gap-2 mb-2">
                                <span className={`h-1.5 w-1.5 rounded-full ${nodeTypeDot.Query}`} />
                                <span className={`text-[11px] px-1.5 py-0.5 rounded border font-mono ${nodeTypeColor.Query}`}>
                                  {q.label}
                                </span>
                                <span className="text-[11px] text-muted-foreground font-mono">stmt {qi}</span>
                                {(q.properties.join_count as number) > 0 && (
                                  <span className="text-[11px] text-muted-foreground font-mono">{q.properties.join_count as number} join{(q.properties.join_count as number) > 1 ? "s" : ""}</span>
                                )}
                                {q.properties.uses_window && (
                                  <span className="text-[11px] font-mono text-purple-600">window fn</span>
                                )}
                              </div>
                              <div className="flex flex-wrap gap-3">
                                {tables.reads.length > 0 && (
                                  <div className="flex flex-wrap items-center gap-1">
                                    <span className="text-[10px] font-mono text-muted-foreground uppercase">reads</span>
                                    {tables.reads.map((t) => {
                                      const tNode = graph.nodes.find((n) => n.type === "Table" && n.label === t);
                                      return (
                                        <span key={t}
                                          className={`text-[11px] px-1.5 py-0.5 rounded border font-mono cursor-pointer hover:opacity-80 ${nodeTypeColor.Table} ${selectedNode?.label === t && selectedNode?.type === "Table" ? "ring-1 ring-success" : ""}`}
                                          onClick={(e) => { if (tNode) selectNode(tNode, e); }}
                                        >{t}</span>
                                      );
                                    })}
                                  </div>
                                )}
                                {tables.writes.length > 0 && (
                                  <div className="flex flex-wrap items-center gap-1">
                                    <span className="text-[10px] font-mono text-muted-foreground uppercase">writes</span>
                                    {tables.writes.map((t) => {
                                      const tNode = graph.nodes.find((n) => n.type === "Table" && n.label === t);
                                      return (
                                        <span key={t}
                                          className={`text-[11px] px-1.5 py-0.5 rounded border font-mono cursor-pointer hover:opacity-80 ${nodeTypeColor.Table} ${selectedNode?.label === t && selectedNode?.type === "Table" ? "ring-1 ring-success" : ""}`}
                                          onClick={(e) => { if (tNode) selectNode(tNode, e); }}
                                        >{t}</span>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>

                {/* Pipeline UDFs */}
                {udfs.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap px-7 py-2.5 bg-orange-50/40 border-t border-orange-100">
                    <GitBranch className="h-3.5 w-3.5 text-orange-500 shrink-0" />
                    <span className="text-[11px] font-mono text-muted-foreground uppercase mr-1">UDFs</span>
                    {udfs.map((u) => {
                      const uNode = graph.nodes.find((n) => n.type === "UDF" && n.label === u);
                      return (
                        <span key={u}
                          className={`text-[11px] px-1.5 py-0.5 rounded border font-mono cursor-pointer hover:opacity-80 ${nodeTypeColor.UDF} ${selectedNode?.label === u && selectedNode?.type === "UDF" ? "ring-1 ring-orange-400" : ""}`}
                          onClick={(e) => { if (uNode) selectNode(uNode, e); }}
                        >{u}</span>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>

    {/* ── Node detail panel ──────────────────────────────────────────────── */}
    {selectedNode && (
      <div className="w-72 shrink-0 rounded-xl border border-border bg-white overflow-hidden sticky top-0 self-start">
        {/* Panel header */}
        <div className={`flex items-center gap-2 px-4 py-3 border-b border-border ${nodeTypeColor[selectedNode.type]}`}>
          <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${nodeTypeDot[selectedNode.type]}`} />
          <span className="text-[12px] font-mono font-semibold flex-1 truncate">{selectedNode.label}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${nodeTypeColor[selectedNode.type]}`}>
            {selectedNode.type}
          </span>
          <button
            onClick={() => setSelectedNode(null)}
            className="ml-1 text-muted-foreground hover:text-foreground text-base leading-none shrink-0"
          >×</button>
        </div>

        {/* Properties */}
        <div className="overflow-y-auto max-h-[70vh]">
          {Object.entries(selectedNode.properties).length === 0 ? (
            <p className="px-4 py-3 text-[12px] text-muted-foreground font-mono">No properties</p>
          ) : (
            <table className="w-full text-[12px]">
              <tbody>
                {Object.entries(selectedNode.properties).map(([k, v]) => {
                  const display = v === null || v === undefined
                    ? <span className="text-muted-foreground/50">null</span>
                    : typeof v === "boolean"
                    ? <span className={v ? "text-success font-semibold" : "text-muted-foreground"}>{String(v)}</span>
                    : typeof v === "object"
                    ? <span className="text-muted-foreground font-mono">{JSON.stringify(v)}</span>
                    : String(v).length > 120
                    ? <span className="text-foreground/80 font-mono break-all">{String(v).slice(0, 120)}…</span>
                    : <span className="text-foreground/80 font-mono break-all">{String(v)}</span>;

                  return (
                    <tr key={k} className="border-b border-border/50 hover:bg-surface-2/30">
                      <td className="px-3 py-1.5 text-muted-foreground font-mono align-top whitespace-nowrap pr-2 w-1/3">{k}</td>
                      <td className="px-3 py-1.5 align-top">{display}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {/* Neo4j element ID */}
          <div className="px-3 py-2 border-t border-border/50">
            <p className="text-[10px] text-muted-foreground/50 font-mono truncate" title={selectedNode.id}>
              id: {selectedNode.id}
            </p>
          </div>
        </div>
      </div>
    )}
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground font-mono mb-1.5">
        {icon}{title}
      </div>
      <div className="flex flex-wrap gap-1">{children}</div>
    </div>
  );
}

function Chip({ label, onClick, clickable }: { label: string; onClick?: () => void; clickable?: boolean }) {
  return (
    <span onClick={onClick}
      className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono bg-surface-2 border border-border text-foreground/80 ${
        clickable ? "cursor-pointer hover:bg-primary/10 hover:border-primary/40 hover:text-primary" : ""
      }`}>
      {label}
    </span>
  );
}
