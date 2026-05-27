import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Badge } from "@/components/AppShell";
import { useState, useRef } from "react";
import { DEMO_FULL_GRAPH } from "@/lib/graph-data";
import { Network, GitBranch, Database, ChevronRight, ListOrdered, Layers } from "lucide-react";

export const Route = createFileRoute("/context-graph")({ component: ContextGraph });

// ── Demo data ─────────────────────────────────────────────────────────────────

const DEMO_PIPELINES = [
  { name:"bronze_ingestion", complexity:"COMPLEX", estimated_effort:"2+ weeks", reads:["external.raw_currency_feed","external.raw_products","external.raw_geolocation_csv","external.raw_customers","external.raw_orders"], writes:["bronze.currency_rates","bronze.products","bronze.geolocation","bronze.store_customers","bronze.store_orders"], udfs:[], depends_on:[], consumed_by:["silver_customers","silver_geolocation","silver_logs","silver_orders","ecomm_sales_mart"] },
  { name:"silver_customers", complexity:"COMPLEX", estimated_effort:"2+ weeks", reads:["bronze.store_customers","bronze.store_orders"], writes:["silver.customers_masked","silver.customer_segments"], udfs:["udf_curate_country","udf_mask_pii"], depends_on:["bronze_ingestion"], consumed_by:["silver_orders","ecomm_sales_mart"] },
  { name:"silver_geolocation", complexity:"COMPLEX", estimated_effort:"2+ weeks", reads:["bronze.geolocation"], writes:["silver.ip_country_lookup","silver.geo_coverage_stats"], udfs:[], depends_on:["bronze_ingestion"], consumed_by:["silver_logs"] },
  { name:"silver_logs", complexity:"COMPLEX", estimated_effort:"2+ weeks", reads:["bronze.web_logs","silver.ip_country_lookup"], writes:["silver.web_logs_enriched","silver.traffic_stats"], udfs:["udf_mask_pii","udf_ip_to_country","udf_curate_country"], depends_on:["silver_geolocation"], consumed_by:["ecomm_sales_mart"] },
  { name:"silver_orders", complexity:"COMPLEX", estimated_effort:"2+ weeks", reads:["bronze.currency_rates","silver.customers_masked","bronze.store_orders","bronze.products","silver.customer_segments"], writes:["silver.order_metrics","silver.orders_enriched","silver.orphan_orders"], udfs:["udf_sales_price_usd"], depends_on:["silver_customers","bronze_ingestion"], consumed_by:["ecomm_sales_mart"] },
  { name:"ecomm_sales_mart", complexity:"COMPLEX", estimated_effort:"2+ weeks", reads:["silver.traffic_stats","silver.orders_enriched","silver.customers_masked","silver.customer_segments","bronze.products","bronze.currency_rates"], writes:["mart.ecomm_sales_summary","mart.country_revenue_report"], udfs:["udf_sales_price_usd"], depends_on:["silver_orders","silver_logs","silver_customers","bronze_ingestion"], consumed_by:[] },
];

const DEMO_PLAN = {
  waves: [
    { wave:0, can_run_parallel:false, pipelines:[{name:"bronze_ingestion",complexity:"COMPLEX",estimated_effort:"2+ weeks",depends_on:[],blast_radius:5,writes:5,udfs:0}] },
    { wave:1, can_run_parallel:true,  pipelines:[{name:"silver_customers",complexity:"COMPLEX",estimated_effort:"2+ weeks",depends_on:["bronze_ingestion"],blast_radius:2,writes:2,udfs:2},{name:"silver_geolocation",complexity:"COMPLEX",estimated_effort:"2+ weeks",depends_on:["bronze_ingestion"],blast_radius:1,writes:2,udfs:0}] },
    { wave:2, can_run_parallel:false, pipelines:[{name:"silver_logs",complexity:"COMPLEX",estimated_effort:"2+ weeks",depends_on:["silver_geolocation"],blast_radius:1,writes:2,udfs:3}] },
    { wave:3, can_run_parallel:false, pipelines:[{name:"silver_orders",complexity:"COMPLEX",estimated_effort:"2+ weeks",depends_on:["silver_customers","bronze_ingestion"],blast_radius:1,writes:3,udfs:1}] },
    { wave:4, can_run_parallel:false, pipelines:[{name:"ecomm_sales_mart",complexity:"COMPLEX",estimated_effort:"2+ weeks",depends_on:["silver_orders","silver_logs","silver_customers","bronze_ingestion"],blast_radius:0,writes:2,udfs:1}] },
  ],
  total_pipelines: 6, error: null,
};


// ── Interfaces ────────────────────────────────────────────────────────────────

interface FullGraphNode { id:string; type:string; label:string; properties:Record<string,unknown>; }
interface FullGraphEdge { id:string; source:string; target:string; type:string; }
interface FullGraph { nodes:FullGraphNode[]; edges:FullGraphEdge[]; error?:string|null; }
interface Pipeline { name:string; complexity:string|null; estimated_effort:string|null; reads:string[]; writes:string[]; udfs:string[]; depends_on:string[]; consumed_by:string[]; }
interface WavePipeline { name:string; complexity:string|null; estimated_effort:string|null; depends_on:string[]; blast_radius:number; writes:number; udfs:number; }
interface Wave { wave:number; can_run_parallel:boolean; pipelines:WavePipeline[]; }

// ── Pipeline DAG helpers ──────────────────────────────────────────────────────

const nodeBg: Record<string,string> = {
  SMALL:"oklch(0.96 0.03 145)",MEDIUM:"oklch(0.95 0.03 235)",
  LARGE:"oklch(0.95 0.06 80)", COMPLEX:"oklch(0.95 0.05 25)",
};
const nodeBorder: Record<string,string> = {
  SMALL:"oklch(0.65 0.15 145)",MEDIUM:"oklch(0.55 0.18 235)",
  LARGE:"oklch(0.70 0.18 80)", COMPLEX:"oklch(0.60 0.20 25)",
};
const complexityTone: Record<string,"success"|"info"|"warning"|"danger"|"neutral"> = {
  SMALL:"success",MEDIUM:"info",LARGE:"warning",COMPLEX:"danger",
};

function computeTiers(pipelines: Pipeline[]): Map<string,number> {
  const tiers = new Map<string,number>();
  const nameSet = new Set(pipelines.map(p => p.name));
  for (const p of pipelines) {
    if (p.depends_on.filter(d => nameSet.has(d)).length === 0) tiers.set(p.name, 0);
  }
  let changed = true;
  while (changed) {
    changed = false;
    for (const p of pipelines) {
      if (tiers.has(p.name)) continue;
      const deps = p.depends_on.filter(d => nameSet.has(d));
      if (deps.every(d => tiers.has(d))) {
        tiers.set(p.name, Math.max(...deps.map(d => tiers.get(d)!)) + 1);
        changed = true;
      }
    }
  }
  for (const p of pipelines) { if (!tiers.has(p.name)) tiers.set(p.name, 0); }
  return tiers;
}

function computeBlastRadius(pipelines: Pipeline[]): Map<string,number> {
  const consumerMap = new Map<string,string[]>();
  for (const p of pipelines) consumerMap.set(p.name, p.consumed_by);
  const blast = new Map<string,number>();
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

// ── Full Graph Visual ─────────────────────────────────────────────────────────

const TYPE_ORDER = ["Pipeline","Workflow","Job","Query","Table","UDF"] as const;

const TYPE_COLORS: Record<string,{fill:string;stroke:string;text:string}> = {
  Pipeline: {fill:"oklch(0.92 0.06 235)",stroke:"oklch(0.55 0.18 235)",text:"oklch(0.25 0.12 235)"},
  Workflow: {fill:"oklch(0.94 0.04 290)",stroke:"oklch(0.55 0.14 290)",text:"oklch(0.30 0.12 290)"},
  Job:      {fill:"oklch(0.94 0.06 80)", stroke:"oklch(0.65 0.18 80)", text:"oklch(0.30 0.12 80)"},
  Query:    {fill:"oklch(0.93 0.05 175)",stroke:"oklch(0.55 0.16 175)",text:"oklch(0.25 0.12 175)"},
  Table:    {fill:"oklch(0.93 0.05 145)",stroke:"oklch(0.55 0.18 145)",text:"oklch(0.25 0.12 145)"},
  UDF:      {fill:"oklch(0.94 0.06 45)", stroke:"oklch(0.65 0.18 45)", text:"oklch(0.30 0.12 45)"},
};

const EDGE_COLORS: Record<string,string> = {
  CONTAINS:"oklch(0.70 0.10 290)", HAS_JOB:"oklch(0.70 0.12 80)",
  HAS_QUERY:"oklch(0.65 0.12 175)", READS:"oklch(0.55 0.18 145)",
  WRITES:"oklch(0.55 0.16 25)",    DEPENDS_ON:"oklch(0.60 0.14 235)",
  USES_UDF:"oklch(0.65 0.14 45)",
};

function FullGraphVisual({ graph }: { graph: FullGraph }) {
  const [hovered,  setHovered]  = useState<string|null>(null);
  const [selected, setSelected] = useState<FullGraphNode|null>(null);

  const NW=130, NH=34, GAP_X=12, GAP_Y=52, ROW_GAP=18, PAD=40, MAX_PER_ROW=10;

  const rows: Partial<Record<string, FullGraphNode[]>> = {};
  for (const t of TYPE_ORDER) rows[t] = graph.nodes.filter(n => n.type === t);

  const svgW = Math.max(1300, MAX_PER_ROW*(NW+GAP_X)-GAP_X + PAD*2);

  const pos = new Map<string,{x:number;y:number}>();
  // Row label positions for each type group
  const typeRowY = new Map<string,number>();
  let y = PAD;
  for (const t of TYPE_ORDER) {
    const group = rows[t] ?? [];
    if (!group.length) continue;
    typeRowY.set(t, y);
    // Split into chunks of MAX_PER_ROW
    for (let ci=0; ci<group.length; ci+=MAX_PER_ROW) {
      const chunk = group.slice(ci, ci+MAX_PER_ROW);
      const rowW = chunk.length*NW + (chunk.length-1)*GAP_X;
      const startX = (svgW - rowW) / 2;
      chunk.forEach((n,i) => pos.set(n.id, {x: startX + i*(NW+GAP_X) + NW/2, y: y + NH/2}));
      y += NH + ROW_GAP;
    }
    y += GAP_Y - ROW_GAP;
  }
  const svgH = y + PAD;

  const connectedIds = new Set<string>();
  if (hovered) {
    connectedIds.add(hovered);
    for (const e of graph.edges) {
      if (e.source === hovered) connectedIds.add(e.target);
      if (e.target === hovered) connectedIds.add(e.source);
    }
  }

  return (
    <div className="flex gap-4 items-start h-full overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden rounded-xl border border-border bg-white shadow-sm">
        <div className="flex items-center gap-4 px-5 py-2.5 border-b border-border flex-wrap shrink-0">
          {TYPE_ORDER.map(t => {
            const count = rows[t]?.length ?? 0;
            if (!count) return null;
            const col = TYPE_COLORS[t];
            return (
              <span key={t} className="inline-flex items-center gap-1.5 text-[11px] font-mono">
                <span className="h-3 w-3 rounded-sm border inline-block" style={{background:col.fill,borderColor:col.stroke}}/>
                <span style={{color:col.text}} className="font-semibold">{count} {t}{count>1?"s":""}</span>
              </span>
            );
          })}
          <span className="ml-auto text-[11px] font-mono text-muted-foreground/60">
            {graph.nodes.length} nodes · {graph.edges.length} edges · hover to highlight
          </span>
        </div>

        <div className="flex-1 overflow-auto">
          <svg width={svgW} height={svgH} style={{display:"block"}}>
            <defs>
              <marker id="fg-arr" markerWidth="5" markerHeight="5" refX="5" refY="2.5" orient="auto">
                <path d="M0,0 L0,5 L5,2.5 z" fill="oklch(0.60 0.04 260 / 0.6)"/>
              </marker>
            </defs>

            {TYPE_ORDER.map(t => {
              if (!(rows[t]?.length)) return null;
              const ry = typeRowY.get(t)!;
              return <text key={t} x={8} y={ry+NH/2+4} fontSize={9} fontFamily="monospace"
                fill="oklch(0.50 0.04 260)" fontWeight="700"
                style={{textTransform:"uppercase",letterSpacing:"0.1em"}}>{t}</text>;
            })}

            {graph.edges.map((e,i) => {
              const from = pos.get(e.source); const to = pos.get(e.target);
              if (!from || !to) return null;
              const isHov = !!hovered && connectedIds.has(e.source) && connectedIds.has(e.target);
              const isDim = !!hovered && !isHov;
              return <line key={i}
                x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke={EDGE_COLORS[e.type] ?? "oklch(0.65 0.04 260)"}
                strokeWidth={isHov ? 1.8 : 0.7}
                strokeOpacity={isDim ? 0.04 : isHov ? 0.9 : 0.2}
                markerEnd="url(#fg-arr)"/>;
            })}

            {graph.nodes.map(n => {
              const p = pos.get(n.id); if (!p) return null;
              const col = TYPE_COLORS[n.type] ?? TYPE_COLORS.Pipeline;
              const isHov = hovered === n.id;
              const isSel = selected?.id === n.id;
              const isDim = !!hovered && !connectedIds.has(n.id);
              const qProps = n.properties as any;
              const rawLabel = n.type === "Query" && qProps.query_id
                ? String(qProps.query_id).split(".").slice(1,-1).join(".") || String(qProps.query_id).split(".").pop()!
                : n.label;
              const label = rawLabel.length > 17 ? rawLabel.slice(0,16)+"…" : rawLabel;
              return (
                <g key={n.id}
                  transform={`translate(${p.x-NW/2},${p.y-NH/2})`}
                  style={{cursor:"pointer", opacity: isDim ? 0.2 : 1}}
                  onMouseEnter={() => setHovered(n.id)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => setSelected(isSel ? null : n)}>
                  <rect width={NW} height={NH} rx={5}
                    fill={col.fill} stroke={isSel ? col.text : col.stroke}
                    strokeWidth={isSel ? 2 : isHov ? 1.5 : 0.8}/>
                  <text x={NW/2} y={NH/2+4} textAnchor="middle" fontSize={9}
                    fontFamily="monospace" fill={col.text}
                    fontWeight={isSel||isHov ? "700":"500"}>{label}</text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {selected && (
        <div className="w-72 shrink-0 rounded-xl border border-border bg-white overflow-hidden sticky top-0 shadow-sm">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border"
            style={{background: TYPE_COLORS[selected.type]?.fill}}>
            <span className="text-[12px] font-mono font-semibold flex-1 truncate"
              style={{color: TYPE_COLORS[selected.type]?.text}}>{selected.label}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded border font-mono"
              style={{color:TYPE_COLORS[selected.type]?.text, borderColor:TYPE_COLORS[selected.type]?.stroke}}>
              {selected.type}
            </span>
            <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground leading-none ml-1">×</button>
          </div>
          <div className="overflow-y-auto max-h-[75vh]">
            <table className="w-full text-[12px]">
              <tbody>
                {Object.entries(selected.properties).map(([k,v]) => (
                  <tr key={k} className="border-b border-border/50 hover:bg-surface-2/30">
                    <td className="px-3 py-1.5 text-muted-foreground font-mono align-top w-1/3 whitespace-nowrap text-[11px]">{k}</td>
                    <td className="px-3 py-1.5 font-mono text-[11px] break-all text-foreground/80">
                      {typeof v==="boolean" ? String(v) :
                        typeof v==="string" && v.length>300 ? v.slice(0,300)+"…" : String(v??"")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Detail helpers for Pipeline DAG ──────────────────────────────────────────

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

function Chip({ label, onClick, clickable }: { label:string; onClick?:()=>void; clickable?:boolean }) {
  return (
    <span onClick={onClick}
      className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono bg-surface-2 border border-border text-foreground/80 ${
        clickable ? "cursor-pointer hover:bg-primary/10 hover:border-primary/40 hover:text-primary" : ""
      }`}>
      {label}
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

function ContextGraph() {
  const [tab,      setTab]      = useState<"fullgraph"|"dag"|"plan">("fullgraph");
  const [selected, setSelected] = useState<Pipeline|null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const pipelines = DEMO_PIPELINES as Pipeline[];
  const tiers     = computeTiers(pipelines);
  const blastMap  = computeBlastRadius(pipelines);
  const maxTier   = pipelines.length ? Math.max(...[...tiers.values()]) : 0;

  const byTier: Pipeline[][] = Array.from({ length: maxTier+1 }, () => []);
  for (const p of pipelines) byTier[tiers.get(p.name) ?? 0].push(p);

  const NODE_W=180, NODE_H=68, TIER_H=120, TIER_PAD=40, GAP=28;
  const maxTierW = Math.max(...byTier.map(t => t.length*NODE_W + (t.length-1)*GAP));
  const svgW = Math.max(960, maxTierW + 120);
  const cx   = svgW / 2;

  const pos = new Map<string,{x:number;y:number}>();
  byTier.forEach((tier, ti) => {
    const totalW = tier.length*NODE_W + (tier.length-1)*GAP;
    const startX = cx - totalW/2;
    tier.forEach((p,pi) => {
      pos.set(p.name, { x: startX + pi*(NODE_W+GAP) + NODE_W/2, y: TIER_PAD + ti*TIER_H + NODE_H/2 });
    });
  });
  const svgH = TIER_PAD*2 + (maxTier+1)*TIER_H;

  const edges: {from:string;to:string}[] = [];
  for (const p of pipelines)
    for (const dep of p.depends_on)
      if (pos.has(dep)) edges.push({from:dep, to:p.name});

  return (
    <AppShell>
      <div className="h-full flex flex-col bg-background overflow-hidden">

        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4 shrink-0">
          <Network className="h-5 w-5 text-info shrink-0"/>
          <div>
            <div className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">Neo4j · Lineage</div>
            <h1 className="text-[18px] font-bold tracking-tight">Pipeline Context Graph</h1>
          </div>

          {/* Tab switcher */}
          <div className="flex items-center gap-1 ml-6 border border-border rounded-lg p-0.5 bg-surface-2/50">
            {([
              ["fullgraph", "Full Graph",      Layers      ],
              ["dag",       "Pipeline DAG",    GitBranch   ],
              ["plan",      "Migration Plan",  ListOrdered ],
            ] as const).map(([id, label, Icon]) => (
              <button key={id} onClick={() => setTab(id)}
                className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-[13px] transition ${
                  tab === id ? "bg-white shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}>
                <Icon className="h-3.5 w-3.5"/>{label}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Badge tone="success">{pipelines.length} pipelines</Badge>
            <Badge tone="neutral">{edges.length} edges</Badge>
          </div>
        </div>

        {/* Full Graph tab */}
        {tab === "fullgraph" && (
          <div className="flex-1 overflow-hidden p-4">
            <FullGraphVisual graph={DEMO_FULL_GRAPH}/>
          </div>
        )}

        {/* Pipeline DAG tab */}
        {tab === "dag" && (
          <div className="flex-1 flex overflow-hidden">
            <div className="flex-1 overflow-auto bg-surface-2/30 relative">
              <div className="absolute left-0 top-0 bottom-0 w-16 pointer-events-none">
                {byTier.map((_,ti) => (
                  <div key={ti} className="absolute left-2 text-[11px] font-mono text-muted-foreground/60 uppercase tracking-wider"
                    style={{top: TIER_PAD + ti*TIER_H}}>T{ti+1}</div>
                ))}
              </div>
              <svg ref={svgRef} width={svgW} height={svgH} className="min-w-full" style={{marginLeft:64}}>
                <defs>
                  <marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto">
                    <path d="M0,0 L0,6 L8,3 z" fill="oklch(0.60 0.012 260)"/>
                  </marker>
                </defs>
                {byTier.map((_,ti) => ti > 0 && (
                  <line key={`sep-${ti}`} x1={0} y1={TIER_PAD+ti*TIER_H-TIER_H/2}
                    x2={svgW} y2={TIER_PAD+ti*TIER_H-TIER_H/2}
                    stroke="oklch(0.88 0.004 260)" strokeDasharray="4 4"/>
                ))}
                {edges.map((e,i) => {
                  const from=pos.get(e.from); const to=pos.get(e.to);
                  if (!from||!to) return null;
                  const my=(from.y+to.y)/2;
                  const isActive = selected && (selected.name===e.from||selected.name===e.to);
                  const dimmed   = selected && !isActive;
                  return <path key={i}
                    d={`M ${from.x} ${from.y+NODE_H/2} C ${from.x} ${my+20}, ${to.x} ${my-20}, ${to.x} ${to.y-NODE_H/2}`}
                    fill="none" stroke="oklch(0.65 0.012 260)"
                    strokeWidth={isActive?2:1} strokeOpacity={dimmed?0.15:0.55}
                    markerEnd="url(#arrow)"/>;
                })}
                {pipelines.map(p => {
                  const {x,y} = pos.get(p.name)!;
                  const cx2 = p.complexity ?? "UNKNOWN";
                  const isActive = selected?.name === p.name;
                  return (
                    <g key={p.name} transform={`translate(${x-NODE_W/2},${y-NODE_H/2})`}
                      onClick={() => setSelected(isActive?null:p)} style={{cursor:"pointer"}}>
                      <rect width={NODE_W} height={NODE_H} rx={6}
                        fill={nodeBg[cx2] ?? "oklch(0.96 0.004 260)"}
                        stroke={isActive ? (nodeBorder[cx2]??"oklch(0.55 0.012 260)") : "oklch(0.88 0.004 260)"}
                        strokeWidth={isActive?2:1}/>
                      <text x={NODE_W/2} y={20} textAnchor="middle" fontSize={11}
                        fontFamily="JetBrains Mono,monospace" fill="oklch(0.25 0.015 260)" fontWeight={600}>
                        {p.name.length>22?p.name.slice(0,21)+"…":p.name}
                      </text>
                      <text x={NODE_W/2} y={36} textAnchor="middle" fontSize={10}
                        fontFamily="JetBrains Mono,monospace" fill="oklch(0.55 0.012 260)">
                        {cx2} · {p.writes.length}w {p.reads.length}r
                      </text>
                      {p.udfs.length>0 && (
                        <text x={NODE_W/2} y={50} textAnchor="middle" fontSize={9}
                          fontFamily="JetBrains Mono,monospace" fill="oklch(0.60 0.12 280)">
                          {p.udfs.length} UDF{p.udfs.length>1?"s":""}
                        </text>
                      )}
                      {(blastMap.get(p.name)??0)>0 && (
                        <text x={NODE_W/2} y={p.udfs.length>0?62:50} textAnchor="middle" fontSize={9}
                          fontFamily="JetBrains Mono,monospace" fill="oklch(0.55 0.20 25)">
                          blast: {blastMap.get(p.name)}
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            </div>

            {selected && (
              <div className="w-80 shrink-0 border-l border-border bg-white overflow-y-auto">
                <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                  <span className="font-mono text-[13px] font-semibold">{selected.name}</span>
                  <button onClick={()=>setSelected(null)} className="text-muted-foreground hover:text-foreground text-lg leading-none">×</button>
                </div>
                <div className="px-4 py-3 space-y-4 text-[13px]">
                  <div className="flex items-center gap-2">
                    <Badge tone={complexityTone[selected.complexity??""]}>{selected.complexity}</Badge>
                    {selected.estimated_effort && <span className="text-muted-foreground">{selected.estimated_effort}</span>}
                  </div>
                  {selected.depends_on.length>0 && (
                    <Section icon={<ChevronRight className="h-3.5 w-3.5 rotate-180 text-info"/>} title="Depends on">
                      {selected.depends_on.map(d=>(
                        <Chip key={d} label={d} clickable onClick={()=>setSelected(pipelines.find(p=>p.name===d)??null)}/>
                      ))}
                    </Section>
                  )}
                  {selected.consumed_by.length>0 && (
                    <Section icon={<ChevronRight className="h-3.5 w-3.5 text-info"/>} title="Consumed by">
                      {selected.consumed_by.map(d=>(
                        <Chip key={d} label={d} clickable onClick={()=>setSelected(pipelines.find(p=>p.name===d)??null)}/>
                      ))}
                    </Section>
                  )}
                  {selected.reads.length>0 && (
                    <Section icon={<Database className="h-3.5 w-3.5 text-muted-foreground"/>} title="Reads">
                      {selected.reads.map(t=><Chip key={t} label={t}/>)}
                    </Section>
                  )}
                  {selected.writes.length>0 && (
                    <Section icon={<Database className="h-3.5 w-3.5 text-success"/>} title="Writes">
                      {selected.writes.map(t=><Chip key={t} label={t}/>)}
                    </Section>
                  )}
                  {selected.udfs.length>0 && (
                    <Section icon={<GitBranch className="h-3.5 w-3.5 text-warning"/>} title="UDFs">
                      {selected.udfs.map(u=><Chip key={u} label={u}/>)}
                    </Section>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Migration Plan tab */}
        {tab === "plan" && (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-3xl mx-auto space-y-6">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-[15px] font-semibold">{DEMO_PLAN.waves.length} migration waves · {DEMO_PLAN.total_pipelines} pipelines</h2>
                <span className="text-[12px] text-muted-foreground font-mono">ordered by dependency depth</span>
              </div>
              {DEMO_PLAN.waves.map(wave => (
                <div key={wave.wave} className="rounded-xl border border-border bg-white overflow-hidden">
                  <div className="flex items-center gap-3 px-5 py-3 bg-surface-2/60 border-b border-border">
                    <div className="h-6 w-6 rounded-full bg-primary/10 flex items-center justify-center text-[12px] font-bold text-primary">
                      {wave.wave+1}
                    </div>
                    <span className="text-[13px] font-semibold">
                      Wave {wave.wave+1}{wave.wave===0?" — migrate first (no dependencies)":""}
                    </span>
                    {wave.can_run_parallel && <Badge tone="info">run in parallel</Badge>}
                    <span className="ml-auto text-[12px] text-muted-foreground font-mono">{wave.pipelines.length} pipeline{wave.pipelines.length!==1?"s":""}</span>
                  </div>
                  <div className="divide-y divide-border">
                    {wave.pipelines.map((p,i) => (
                      <div key={p.name} className="flex items-center gap-4 px-5 py-3.5 hover:bg-surface-2/30">
                        <span className="text-[11px] text-muted-foreground/50 font-mono w-4">{i+1}</span>
                        <div className="flex-1">
                          <div className="text-[14px] font-semibold">{p.name}</div>
                          {p.depends_on.length>0 && <div className="text-[12px] text-muted-foreground font-mono">depends on: {p.depends_on.join(", ")}</div>}
                        </div>
                        <div className="flex items-center gap-2">
                          {p.complexity && <Badge tone={p.complexity==="SMALL"?"success":p.complexity==="MEDIUM"?"info":p.complexity==="LARGE"?"warning":"danger"}>{p.complexity}</Badge>}
                          {p.estimated_effort && <span className="text-[12px] text-muted-foreground font-mono">{p.estimated_effort}</span>}
                          {p.blast_radius>0 && <span className="text-[11px] px-2 py-0.5 rounded bg-danger/8 text-danger border border-danger/20 font-mono">blast: {p.blast_radius}</span>}
                          {p.udfs>0 && <span className="text-[11px] px-2 py-0.5 rounded bg-warning/8 text-warning border border-warning/20 font-mono">{p.udfs} UDF{p.udfs>1?"s":""}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </AppShell>
  );
}
