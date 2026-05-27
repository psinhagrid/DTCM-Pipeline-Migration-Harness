import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Badge } from "@/components/AppShell";
import { useState } from "react";
import { DEMO_FULL_GRAPH } from "@/lib/graph-data";
import { Network, ListOrdered, Layers } from "lucide-react";

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
  Pipeline: {fill:"#2563eb", stroke:"#1d4ed8", text:"#ffffff"},
  Workflow: {fill:"#7c3aed", stroke:"#6d28d9", text:"#ffffff"},
  Job:      {fill:"#d97706", stroke:"#b45309", text:"#ffffff"},
  Query:    {fill:"#0d9488", stroke:"#0f766e", text:"#ffffff"},
  Table:    {fill:"#16a34a", stroke:"#15803d", text:"#ffffff"},
  UDF:      {fill:"#dc2626", stroke:"#b91c1c", text:"#ffffff"},
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

  const R=22, PAD=60;
  const svgW=1300, svgH=720;

  // Seeded scatter — consistent positions, not rigid rows
  const pos = new Map<string,{x:number;y:number}>();
  const placed: {x:number;y:number}[] = [];
  let seed = 42;
  const rand = () => { seed = (seed*1664525 + 1013904223) & 0xffffffff; return (seed >>> 0) / 0xffffffff; };

  for (const n of graph.nodes) {
    let x=0, y=0, tries=0;
    do {
      x = PAD + rand() * (svgW - PAD*2);
      y = PAD + rand() * (svgH - PAD*2);
      tries++;
    } while (tries < 80 && placed.some(p => Math.hypot(p.x-x, p.y-y) < R*2.8));
    pos.set(n.id, {x, y});
    placed.push({x, y});
  }

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
        <div className="flex items-center gap-4 px-5 py-3 border-b border-border shrink-0">
          <span className="text-[11px] font-mono text-muted-foreground/50 shrink-0">{graph.nodes.length} nodes · {graph.edges.length} edges · hover to highlight</span>
          <div className="ml-auto flex items-center gap-5 flex-wrap justify-end">
            {TYPE_ORDER.map(t => {
              const count = graph.nodes.filter(n => n.type===t).length;
              if (!count) return null;
              const col = TYPE_COLORS[t];
              return (
                <div key={t} className="flex flex-col items-center gap-1">
                  <svg width="16" height="16"><circle cx="8" cy="8" r="7" fill={col.fill} stroke={col.stroke} strokeWidth="1.5"/></svg>
                  <span className="text-[9px] font-mono font-semibold text-foreground/70 uppercase tracking-wide leading-none">{t}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          <svg width={svgW} height={svgH} style={{display:"block"}}>
            <defs>
              <marker id="arr-blue" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L0,7 L7,3.5 z" fill="#93c5fd" opacity="0.8"/></marker>
              <marker id="arr-orange" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L0,7 L7,3.5 z" fill="#fcd34d" opacity="0.8"/></marker>
              <marker id="arr-red" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L0,7 L7,3.5 z" fill="#fca5a5" opacity="0.8"/></marker>
              <marker id="arr-gray" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L0,7 L7,3.5 z" fill="#94a3b8" opacity="0.7"/></marker>
            </defs>



            {graph.edges.map((e,i) => {
              const from = pos.get(e.source); const to = pos.get(e.target);
              if (!from || !to) return null;
              const isHov = !!hovered && connectedIds.has(e.source) && connectedIds.has(e.target);
              const isDim = !!hovered && !isHov;
              const mx=(from.x+to.x)/2, my=(from.y+to.y)/2;
              const dx=to.x-from.x, dy=to.y-from.y, len=Math.hypot(dx,dy)||1;
              const cx=mx-(dy/len)*len*0.15, cy=my+(dx/len)*len*0.15;
              const isRed = e.type==="USES_UDF"||e.type==="DEPENDS_ON";
              const isOrange = e.type==="READS"||e.type==="WRITES";
              const isBlue = e.type==="CONTAINS"||e.type==="HAS_JOB"||e.type==="HAS_QUERY";
              const edgeColor = isRed ? "#fca5a5" : isOrange ? "#fcd34d" : isBlue ? "#93c5fd" : "#cbd5e1";
              const arrId = isRed ? "arr-red" : isOrange ? "arr-orange" : isBlue ? "arr-blue" : "arr-gray";
              const dashed = isOrange || isRed;
              return <path key={i}
                d={`M ${from.x} ${from.y} Q ${cx} ${cy} ${to.x} ${to.y}`}
                fill="none"
                stroke={edgeColor}
                strokeWidth={isHov ? 2.5 : 1.2}
                strokeDasharray={dashed ? "6 4" : "none"}
                strokeOpacity={isDim ? 0.04 : isHov ? 1 : 0.35}
                markerEnd={`url(#${arrId})`}/>;
            })}

            {graph.nodes.map(n => {
              const p = pos.get(n.id); if (!p) return null;
              const col = TYPE_COLORS[n.type] ?? TYPE_COLORS.Pipeline;
              const isHov = hovered === n.id;
              const isSel = selected?.id === n.id;
              const isDim = !!hovered && !connectedIds.has(n.id);
              const qProps = n.properties as any;
              const rawLabel = n.type === "Query" && qProps.query_id
                ? String(qProps.query_id).split(".").slice(1,-1).join(".") || n.label
                : n.label;
              const shortLabel = rawLabel.length > 9 ? rawLabel.slice(0,8)+"…" : rawLabel;
              return (
                <g key={n.id}
                  transform={`translate(${p.x},${p.y})`}
                  style={{cursor:"pointer", opacity: isDim ? 0.15 : 1}}
                  onMouseEnter={() => setHovered(n.id)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => setSelected(isSel ? null : n)}>
                  <circle r={R}
                    fill={col.fill}
                    stroke={isSel ? col.text : isHov ? col.stroke : col.stroke}
                    strokeWidth={isSel ? 2.5 : isHov ? 2 : 0.8}/>
                  <text textAnchor="middle" y={4} fontSize={7}
                    fontFamily="monospace" fill={col.text}
                    fontWeight={isSel||isHov ? "700":"500"}>{shortLabel}</text>
                  {(isHov || isSel) && (
                    <text textAnchor="middle" y={R+10} fontSize={8}
                      fontFamily="monospace" fill={col.text} fontWeight="600">
                      {rawLabel.length > 20 ? rawLabel.slice(0,19)+"…" : rawLabel}
                    </text>
                  )}
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
  const [tab,      setTab]      = useState<"fullgraph"|"plan">("fullgraph");
  const [selected, setSelected] = useState<Pipeline|null>(null);
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
            <Badge tone="success">{DEMO_FULL_GRAPH.nodes.length} nodes</Badge>
            <Badge tone="neutral">{DEMO_FULL_GRAPH.edges.length} edges</Badge>
          </div>
        </div>

        {/* Full Graph tab */}
        {tab === "fullgraph" && (
          <div className="flex-1 overflow-hidden p-4">
            <FullGraphVisual graph={DEMO_FULL_GRAPH}/>
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
