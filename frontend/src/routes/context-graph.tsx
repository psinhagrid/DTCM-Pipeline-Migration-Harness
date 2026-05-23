import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Badge } from "@/components/AppShell";
import { useEffect, useState, useRef } from "react";
import { Network, GitBranch, Database, Cpu, ChevronRight, AlertCircle } from "lucide-react";

export const Route = createFileRoute("/context-graph")({ component: ContextGraph });

// ── Types ─────────────────────────────────────────────────────────────────────

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

interface GraphData {
  pipelines: Pipeline[];
  error: string | null;
}

// ── Complexity colours ────────────────────────────────────────────────────────

const complexityTone: Record<string, "success" | "info" | "warning" | "danger" | "neutral"> = {
  SMALL:   "success",
  MEDIUM:  "info",
  LARGE:   "warning",
  COMPLEX: "danger",
};

const complexityBg: Record<string, string> = {
  SMALL:   "bg-success/10 border-success/30",
  MEDIUM:  "bg-info/10 border-info/30",
  LARGE:   "bg-warning/10 border-warning/30",
  COMPLEX: "bg-danger/10 border-danger/30",
};

// ── Topology helpers ──────────────────────────────────────────────────────────

function computeTiers(pipelines: Pipeline[]): Map<string, number> {
  const tiers = new Map<string, number>();
  const nameSet = new Set(pipelines.map((p) => p.name));

  // Assign tier 0 to pipelines with no in-graph dependencies
  for (const p of pipelines) {
    const deps = p.depends_on.filter((d) => nameSet.has(d));
    if (deps.length === 0) tiers.set(p.name, 0);
  }

  // Iteratively propagate tier = max(dep tier) + 1
  let changed = true;
  while (changed) {
    changed = false;
    for (const p of pipelines) {
      if (tiers.has(p.name)) continue;
      const deps = p.depends_on.filter((d) => nameSet.has(d));
      if (deps.every((d) => tiers.has(d))) {
        const tier = Math.max(...deps.map((d) => tiers.get(d)!)) + 1;
        tiers.set(p.name, tier);
        changed = true;
      }
    }
  }
  // Any remaining unresolved (cycles) get tier 0
  for (const p of pipelines) {
    if (!tiers.has(p.name)) tiers.set(p.name, 0);
  }
  return tiers;
}

// ── Main component ────────────────────────────────────────────────────────────

function ContextGraph() {
  const [data,     setData]     = useState<GraphData | null>(null);
  const [selected, setSelected] = useState<Pipeline | null>(null);
  const [loading,  setLoading]  = useState(true);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    fetch("/graph")
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => { setData({ pipelines: [], error: "Could not reach backend" }); setLoading(false); });
  }, []);

  const pipelines = data?.pipelines ?? [];
  const tiers     = computeTiers(pipelines);
  const maxTier   = pipelines.length ? Math.max(...[...tiers.values()]) : 0;

  // Group by tier
  const byTier: Pipeline[][] = Array.from({ length: maxTier + 1 }, () => []);
  for (const p of pipelines) byTier[tiers.get(p.name) ?? 0].push(p);

  // Node position map (for SVG arrows) — computed after layout
  const nodePos = useRef<Map<string, { x: number; y: number }>>(new Map());

  const NODE_W = 180;
  const NODE_H = 56;
  const TIER_H = 120;
  const TIER_PADDING = 40;

  function positionNodes() {
    const pos = new Map<string, { x: number; y: number }>();
    byTier.forEach((tier, ti) => {
      const totalW = tier.length * NODE_W + (tier.length - 1) * 24;
      const startX = Math.max(0, 600 - totalW / 2);
      tier.forEach((p, pi) => {
        pos.set(p.name, {
          x: startX + pi * (NODE_W + 24) + NODE_W / 2,
          y: TIER_PADDING + ti * TIER_H + NODE_H / 2,
        });
      });
    });
    nodePos.current = pos;
    return pos;
  }

  const pos = positionNodes();
  const svgH = TIER_PADDING * 2 + (maxTier + 1) * TIER_H;
  const svgW = Math.max(800, ...byTier.map((t) => t.length * (NODE_W + 24)));

  // Build edge list
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
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Neo4j</div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5">Pipeline Lineage Graph</h1>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <Badge tone={pipelines.length > 0 ? "success" : "neutral"}>
              {pipelines.length > 0 ? `${pipelines.length} pipelines` : "empty graph"}
            </Badge>
            <Badge tone="neutral">{edges.length} dependencies</Badge>
          </div>
        </div>

        {loading && (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <Cpu className="h-6 w-6 animate-spin mr-3" /> Querying Neo4j…
          </div>
        )}

        {!loading && data?.error && (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-3">
            <AlertCircle className="h-10 w-10 text-warning" />
            <p className="text-[15px] font-medium text-foreground">Neo4j not reachable</p>
            <p className="text-[13px] text-muted-foreground max-w-sm">
              {data.error}. Run a pipeline first to populate the graph, or start Neo4j with:
            </p>
            <code className="text-[12px] bg-surface-2 px-3 py-2 rounded font-mono text-foreground">
              docker run --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/dtcm_local --detach neo4j:5
            </code>
          </div>
        )}

        {!loading && !data?.error && pipelines.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-2">
            <Network className="h-10 w-10 opacity-30" />
            <p className="text-[15px]">Graph is empty</p>
            <p className="text-[13px]">Run pipeline assessments to populate the lineage graph.</p>
          </div>
        )}

        {!loading && pipelines.length > 0 && (
          <div className="flex-1 flex overflow-hidden">
            {/* DAG canvas */}
            <div className="flex-1 overflow-auto bg-surface-2/30 relative">
              {/* Tier labels */}
              <div className="absolute left-0 top-0 bottom-0 w-16 pointer-events-none">
                {byTier.map((_, ti) => (
                  <div
                    key={ti}
                    className="absolute left-2 text-[11px] font-mono text-muted-foreground/60 uppercase tracking-wider"
                    style={{ top: TIER_PADDING + ti * TIER_H }}
                  >
                    T{ti + 1}
                  </div>
                ))}
              </div>

              <svg
                ref={svgRef}
                width={svgW}
                height={svgH}
                className="min-w-full"
                style={{ marginLeft: 64 }}
              >
                <defs>
                  <marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto">
                    <path d="M0,0 L0,6 L8,3 z" fill="oklch(0.60 0.012 260)" />
                  </marker>
                </defs>

                {/* Tier separator lines */}
                {byTier.map((_, ti) => ti > 0 && (
                  <line
                    key={`sep-${ti}`}
                    x1={0} y1={TIER_PADDING + ti * TIER_H - TIER_H / 2}
                    x2={svgW} y2={TIER_PADDING + ti * TIER_H - TIER_H / 2}
                    stroke="oklch(0.88 0.004 260)" strokeDasharray="4 4"
                  />
                ))}

                {/* Dependency edges */}
                {edges.map((e, i) => {
                  const from = pos.get(e.from);
                  const to   = pos.get(e.to);
                  if (!from || !to) return null;
                  const mx = (from.x + to.x) / 2;
                  const my = (from.y + to.y) / 2;
                  return (
                    <g key={i}>
                      <path
                        d={`M ${from.x} ${from.y + NODE_H / 2} C ${from.x} ${my + 20}, ${to.x} ${my - 20}, ${to.x} ${to.y - NODE_H / 2}`}
                        fill="none"
                        stroke="oklch(0.65 0.012 260)"
                        strokeWidth={selected && (selected.name === e.from || selected.name === e.to) ? 2 : 1}
                        strokeOpacity={selected && selected.name !== e.from && selected.name !== e.to ? 0.2 : 0.6}
                        markerEnd="url(#arrow)"
                      />
                    </g>
                  );
                })}

                {/* Pipeline nodes */}
                {pipelines.map((p) => {
                  const { x, y } = pos.get(p.name)!;
                  const cx       = p.complexity ?? "UNKNOWN";
                  const isActive = selected?.name === p.name;
                  const bgColors: Record<string, string> = {
                    SMALL: "oklch(0.96 0.03 145)", MEDIUM: "oklch(0.95 0.03 235)",
                    LARGE: "oklch(0.95 0.06 80)",  COMPLEX: "oklch(0.95 0.05 25)",
                  };
                  const borderColors: Record<string, string> = {
                    SMALL: "oklch(0.65 0.15 145)", MEDIUM: "oklch(0.55 0.18 235)",
                    LARGE: "oklch(0.70 0.18 80)",  COMPLEX: "oklch(0.60 0.20 25)",
                  };
                  return (
                    <g
                      key={p.name}
                      transform={`translate(${x - NODE_W / 2}, ${y - NODE_H / 2})`}
                      onClick={() => setSelected(isActive ? null : p)}
                      style={{ cursor: "pointer" }}
                    >
                      <rect
                        width={NODE_W} height={NODE_H} rx={6}
                        fill={bgColors[cx] ?? "oklch(0.96 0.004 260)"}
                        stroke={isActive ? (borderColors[cx] ?? "oklch(0.55 0.012 260)") : "oklch(0.88 0.004 260)"}
                        strokeWidth={isActive ? 2 : 1}
                      />
                      <text x={NODE_W / 2} y={20} textAnchor="middle" fontSize={11} fontFamily="JetBrains Mono, monospace" fill="oklch(0.25 0.015 260)" fontWeight={600}>
                        {p.name.length > 22 ? p.name.slice(0, 21) + "…" : p.name}
                      </text>
                      <text x={NODE_W / 2} y={36} textAnchor="middle" fontSize={10} fontFamily="JetBrains Mono, monospace" fill="oklch(0.55 0.012 260)">
                        {cx} · {p.writes.length}w {p.reads.length}r
                      </text>
                      {p.udfs.length > 0 && (
                        <text x={NODE_W / 2} y={50} textAnchor="middle" fontSize={9} fontFamily="JetBrains Mono, monospace" fill="oklch(0.60 0.12 280)">
                          {p.udfs.length} UDF{p.udfs.length > 1 ? "s" : ""}
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
                  <span className="font-mono text-[13px] font-semibold text-foreground">{selected.name}</span>
                  <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground text-[18px] leading-none">×</button>
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
                        <Chip key={d} label={d} onClick={() => setSelected(pipelines.find((p) => p.name === d) ?? null)} clickable />
                      ))}
                    </Section>
                  )}

                  {selected.consumed_by.length > 0 && (
                    <Section icon={<ChevronRight className="h-3.5 w-3.5 text-info" />} title="Consumed by">
                      {selected.consumed_by.map((d) => (
                        <Chip key={d} label={d} onClick={() => setSelected(pipelines.find((p) => p.name === d) ?? null)} clickable />
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

// ── Sub-components ────────────────────────────────────────────────────────────

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
    <span
      onClick={onClick}
      className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono bg-surface-2 border border-border text-foreground/80 ${clickable ? "cursor-pointer hover:bg-primary/10 hover:border-primary/40 hover:text-primary" : ""}`}
    >
      {label}
    </span>
  );
}
