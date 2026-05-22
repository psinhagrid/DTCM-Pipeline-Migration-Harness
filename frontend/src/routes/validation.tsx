import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel, Badge } from "@/components/AppShell";
import { useEffect, useState } from "react";
import {
  ShieldCheck, ShieldAlert, ShieldX, ChevronDown, ChevronRight,
  AlertTriangle, Lightbulb,
} from "lucide-react";
import { onReset } from "@/lib/reset-store";

export const Route = createFileRoute("/validation")({ component: Validation });

// ── Constants ─────────────────────────────────────────────────────────────────

const CHECK_LABELS: Record<string, string> = {
  table_parity:       "Table Parity",
  column_parity:      "Column Parity",
  aggregation_parity: "Aggregation Parity",
  join_parity:        "Join Parity",
  group_by_parity:    "Group-By Parity",
  filter_parity:      "Filter Parity",
  partition_parity:   "Partition Parity",
  runtime_var_parity: "Runtime Variables",
  workflow_parity:    "Workflow Parity",
  row_count:          "Row Count",
  checksum:           "Checksum",
  sla_compliance:     "SLA Compliance",
  consumer_replay:    "Consumer Replay",
};

const SEV_CONFIG: Record<string, { color: string; bg: string; border: string }> = {
  CRITICAL: { color: "text-red-700",    bg: "bg-red-50",    border: "border-red-200" },
  HIGH:     { color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-200" },
  MEDIUM:   { color: "text-yellow-700", bg: "bg-yellow-50", border: "border-yellow-200" },
  LOW:      { color: "text-blue-700",   bg: "bg-blue-50",   border: "border-blue-200" },
  INFO:     { color: "text-gray-500",   bg: "bg-gray-50",   border: "border-gray-200" },
};

const RISK_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  CRITICAL: { color: "text-red-700",    bg: "bg-red-50",     label: "CRITICAL" },
  HIGH:     { color: "text-orange-700", bg: "bg-orange-50",  label: "HIGH" },
  MODERATE: { color: "text-yellow-700", bg: "bg-yellow-50",  label: "MODERATE" },
  LOW:      { color: "text-blue-700",   bg: "bg-blue-50",    label: "LOW" },
  MINIMAL:  { color: "text-green-700",  bg: "bg-green-50",   label: "MINIMAL" },
};

function statusTone(s: string): "success" | "warning" | "danger" | "neutral" {
  if (s === "PASSED") return "success";
  if (s === "WARNING" || s === "PARTIAL") return "warning";
  if (s === "FAILED") return "danger";
  return "neutral";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SeverityBadge({ level }: { level: string }) {
  const cfg = SEV_CONFIG[level] || SEV_CONFIG.INFO;
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase border ${cfg.color} ${cfg.bg} ${cfg.border}`}>
      {level}
    </span>
  );
}

// Feature 4: Semantic breakdown bar
function SemanticBreakdown({ data }: { data: Record<string, number> }) {
  const items = [
    { key: "tables",       label: "Tables" },
    { key: "columns",      label: "Columns" },
    { key: "aggregations", label: "Aggregations" },
    { key: "joins",        label: "Joins" },
    { key: "filters",      label: "Filters" },
    { key: "runtime_vars", label: "Runtime Vars" },
    { key: "partitions",   label: "Partitions" },
  ];
  return (
    <Panel eyebrow="Feature 4" title="Semantic Similarity Breakdown">
      <div className="p-5 space-y-4">
        {items.map(({ key, label }) => {
          const pct = data?.[key] ?? 100;
          const color = pct === 100 ? "bg-green-500" : pct >= 80 ? "bg-yellow-500" : "bg-red-500";
          return (
            <div key={key}>
              <div className="flex justify-between text-[13px] mb-1">
                <span className="text-muted-foreground">{label}</span>
                <span className={`font-mono font-semibold ${pct === 100 ? "text-green-600" : pct >= 80 ? "text-yellow-600" : "text-red-600"}`}>
                  {pct}%
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// Feature 5: Migration Risk
function MigrationRisk({ risk, score }: { risk: string; score: number }) {
  const cfg = RISK_CONFIG[risk] || RISK_CONFIG.MINIMAL;
  return (
    <Panel eyebrow="Feature 5" title="Migration Risk">
      <div className="p-4">
        <div className={`rounded-lg border p-4 ${cfg.bg} ${cfg.color}`} style={{ borderColor: "currentColor", borderOpacity: 0.3 }}>
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-6 w-6 shrink-0" />
            <div>
              <div className="text-[13px] opacity-70 uppercase tracking-wider font-mono">Risk Level</div>
              <div className="text-[22px] font-bold tracking-tight">{cfg.label}</div>
            </div>
            <div className="ml-auto text-right">
              <div className="text-[13px] opacity-70 font-mono">Risk Score</div>
              <div className="text-[22px] font-bold">{score}</div>
            </div>
          </div>
        </div>
        <p className="mt-3 text-[13px] text-muted-foreground">
          Calculated from row variance, semantic parity, missing partitions, and runtime variable mappings.
        </p>
      </div>
    </Panel>
  );
}

// Feature 3: Migration Recommendation
function Recommendation({ rec }: { rec: { action: string; conditions: string[] } }) {
  return (
    <Panel eyebrow="Feature 3" title="Migration Recommendation">
      <div className="p-4 space-y-3">
        <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-50 border border-blue-200">
          <Lightbulb className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
          <div className="text-[14px] font-semibold text-blue-800">{rec?.action}</div>
        </div>
        {rec?.conditions?.length > 0 && (
          <div>
            <div className="text-[12px] uppercase tracking-wider text-muted-foreground font-mono mb-2">Conditions</div>
            <ul className="space-y-1.5">
              {rec.conditions.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-[13.5px]">
                  <span className="text-orange-500 mt-0.5 shrink-0">→</span>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Panel>
  );
}

// Feature 1: Agent Reasoning Panel
function ReasoningPanel({ lines }: { lines: { agent: string; message: string }[] }) {
  const colors: Record<string, string> = {
    RECONCILE: "text-blue-700",
    SUPERVISOR: "text-purple-700",
  };
  return (
    <Panel eyebrow="Feature 1" title="Agent Reasoning">
      <div className="p-5 space-y-3 font-mono">
        {lines?.map((line, i) => (
          <div key={i} className="flex gap-3 text-[14px] leading-relaxed">
            <span className={`shrink-0 font-bold ${colors[line.agent] || "text-foreground"}`}>
              [{line.agent}]
            </span>
            <span className="text-foreground/80">{line.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// Feature 7: Expandable Issue Details
function IssueCard({ issue, detail }: { issue: string; detail: any }) {
  const [open, setOpen] = useState(false);
  const hasSrc = detail?.source_snippet || detail?.converted_snippet;

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-red-100 transition"
      >
        {hasSrc
          ? <ChevronRight className={`h-4 w-4 text-red-500 transition-transform shrink-0 ${open ? "rotate-90" : ""}`} />
          : <span className="h-4 w-4 shrink-0" />
        }
        <span className="text-[13px] font-mono text-red-800 flex-1">{issue}</span>
      </button>

      {open && hasSrc && (
        <div className="border-t border-red-200 grid grid-cols-2 divide-x divide-red-200">
          <div className="p-4">
            <div className="text-[11px] uppercase tracking-wider text-red-500 font-mono mb-2">Source</div>
            <pre className="text-[12.5px] font-mono text-foreground/80 whitespace-pre-wrap leading-relaxed">
              {detail.source_snippet || "—"}
            </pre>
          </div>
          <div className="p-4">
            <div className="text-[11px] uppercase tracking-wider text-orange-500 font-mono mb-2">Converted</div>
            <pre className="text-[12.5px] font-mono text-foreground/80 whitespace-pre-wrap leading-relaxed">
              {detail.converted_snippet || "—"}
            </pre>
            {detail.missing?.length > 0 && (
              <div className="mt-3 pt-2 border-t border-red-200">
                <div className="text-[11px] uppercase tracking-wider text-red-500 font-mono mb-1">Missing</div>
                {detail.missing.map((m: string, i: number) => (
                  <div key={i} className="text-[12px] font-mono text-red-700">{m}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function Validation() {
  const [pipelines, setPipelines] = useState<string[]>([]);
  const [pipeline, setPipeline]   = useState("");
  const [data, setData]           = useState<any>(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState("");

  useEffect(() => {
    fetch("/pipelines")
      .then((r) => r.json())
      .then(({ pipelines: pl }) => { setPipelines(pl); if (pl.length) setPipeline(pl[0]); });
  }, []);

  // Listen for global reset
  useEffect(() => onReset(() => {
    setData(null);
    setError("");
  }), []);

  useEffect(() => {
    if (!pipeline) return;
    setLoading(true); setError(""); setData(null);
    fetch(`/reconcile/${encodeURIComponent(pipeline)}`)
      .then((r) => { if (!r.ok) throw new Error("No reconciliation data yet"); return r.json(); })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [pipeline]);

  const status = data?.validation_status || "—";
  const tone   = statusTone(status);

  return (
    <AppShell>
      <div className="h-full overflow-y-auto bg-background">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4">
          <div>
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Validation & Reconciliation</div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5">Migration Certification</h1>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <div className="relative">
              <select
                value={pipeline} onChange={(e) => setPipeline(e.target.value)}
                className="h-10 pl-4 pr-9 rounded-lg border border-border bg-white text-[14px] appearance-none cursor-pointer focus:outline-none focus:border-primary"
              >
                {pipelines.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            </div>
            {data && <Badge tone={tone}>{status}</Badge>}
          </div>
        </div>

        {loading && <div className="p-12 text-center text-[15px] text-muted-foreground">Loading reconciliation data…</div>}
        {!loading && error && (
          <div className="p-12 text-center">
            <p className="text-[16px] text-muted-foreground">{error}</p>
            <p className="text-[14px] text-muted-foreground mt-2">Run the pipeline from Dashboard first.</p>
          </div>
        )}

        {!loading && data && (
          <div className="p-8 space-y-8">

            {/* Row 1: Status + Risk + Recommendation */}
            <div className="grid grid-cols-12 gap-6">

              {/* Status card */}
              <div className="col-span-12 lg:col-span-4">
                <Panel eyebrow="Certification" title="Migration governance">
                  <div className="p-5">
                    <div className={`rounded-xl border p-5 ${
                      tone === "success" ? "border-green-300 bg-green-50" :
                      tone === "warning" ? "border-yellow-300 bg-yellow-50" :
                                          "border-red-300 bg-red-50"
                    }`}>
                      <div className="flex items-center gap-3">
                        {tone === "success" && <ShieldCheck className="h-8 w-8 text-green-600" />}
                        {tone === "warning" && <ShieldAlert className="h-8 w-8 text-yellow-600" />}
                        {tone === "danger"  && <ShieldX     className="h-8 w-8 text-red-600"   />}
                        <div className="flex-1">
                          <div className="text-[13px] text-muted-foreground font-mono">Status</div>
                          <div className="text-[22px] font-bold">{status}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-[13px] text-muted-foreground font-mono">Confidence</div>
                          <div className="text-[22px] font-bold">{((data.confidence_score || 0) * 100).toFixed(0)}%</div>
                        </div>
                      </div>
                      <div className="mt-4 h-2 bg-white/60 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${tone === "success" ? "bg-green-500" : tone === "warning" ? "bg-yellow-500" : "bg-red-500"}`}
                          style={{ width: `${(data.confidence_score || 0) * 100}%` }} />
                      </div>
                    </div>
                    <dl className="mt-5 space-y-2.5 text-[14px]">
                      {[
                        { k: "pipeline",        v: data.pipeline },
                        { k: "files reviewed",  v: data.files_reconciled },
                        { k: "source rows",     v: (data.source_rows || 0).toLocaleString() },
                        { k: "target rows",     v: (data.target_rows || 0).toLocaleString() },
                        { k: "row variance",    v: `${data.row_variance_pct ?? 0}%` },
                        { k: "speedup",         v: `${data.speedup_factor ?? "—"}×` },
                        { k: "semantic sim.",   v: `${((data.semantic_similarity || 0) * 100).toFixed(0)}%` },
                      ].map(({ k, v }) => (
                        <div key={k} className="flex justify-between border-b border-border/60 pb-2">
                          <span className="text-muted-foreground font-mono">{k}</span>
                          <span className="font-medium">{v}</span>
                        </div>
                      ))}
                    </dl>
                  </div>
                </Panel>
              </div>

              {/* Risk + Recommendation stacked */}
              <div className="col-span-12 lg:col-span-4 space-y-5">
                <MigrationRisk risk={data.migration_risk || "MINIMAL"} score={data.migration_risk_score || 0} />
                <Recommendation rec={data.recommendation} />
              </div>

              {/* Semantic breakdown */}
              <div className="col-span-12 lg:col-span-4">
                <SemanticBreakdown data={data.semantic_breakdown || {}} />
              </div>
            </div>

            {/* Row 2: Checks table + Reasoning */}
            <div className="grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-8">
                <Panel eyebrow="Checks · Feature 2" title="Reconciliation parity + severity">
                  <ul className="divide-y divide-border">
                    {Object.entries(data.checks || {}).map(([key, status]: [string, any]) => {
                      const detail   = data.check_details?.[key]?.detail || "";
                      const score    = data.check_details?.[key]?.score;
                      const severity = data.severity_map?.[key] || "INFO";
                      const t        = statusTone(status);
                      return (
                        <li key={key} className="flex items-center gap-4 px-6 py-4 hover:bg-surface-2/40">
                          <span className={`text-[18px] shrink-0 ${t === "success" ? "text-green-600" : t === "warning" ? "text-yellow-600" : t === "danger" ? "text-red-600" : "text-muted-foreground"}`}>
                            {status === "PASSED" ? "✓" : status === "SKIPPED" ? "–" : status === "WARNING" ? "⚠" : "✗"}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="text-[15px] font-medium">{CHECK_LABELS[key] || key}</div>
                            {detail && <div className="text-[13px] text-muted-foreground mt-0.5 truncate">{detail}</div>}
                          </div>
                          <SeverityBadge level={severity} />
                          {score !== undefined && status !== "SKIPPED" && (
                            <div className="w-20 shrink-0 hidden md:block">
                              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${
                                  t === "success" ? "bg-green-500" :
                                  t === "warning" ? "bg-yellow-500" :
                                  t === "danger"  ? "bg-red-500"   :
                                  "bg-gray-300"
                                }`}
                                  style={{ width: `${(score as number) * 100}%` }} />
                              </div>
                              <div className="text-[11px] text-muted-foreground text-right mt-0.5">
                                {((score as number) * 100).toFixed(0)}%
                              </div>
                            </div>
                          )}
                          <Badge tone={t}>{status}</Badge>
                        </li>
                      );
                    })}
                  </ul>
                </Panel>
              </div>

              {/* Reasoning panel */}
              <div className="col-span-12 lg:col-span-4">
                <ReasoningPanel lines={data.reasoning || []} />
              </div>
            </div>

            {/* Row 3: Expandable issues */}
            {(data.issues?.length > 0) && (
              <Panel eyebrow="Feature 7" title={`${data.issues.length} Issue(s) — Expandable Details`}>
                <div className="p-4 space-y-3">
                  {data.issues.map((issue: string, i: number) => (
                    <IssueCard
                      key={i}
                      issue={issue}
                      detail={data.issue_details?.[issue]}
                    />
                  ))}
                </div>
              </Panel>
            )}

          </div>
        )}
      </div>
    </AppShell>
  );
}
