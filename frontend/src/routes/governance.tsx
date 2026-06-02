import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel, Badge } from "@/components/AppShell";
import { useEffect, useState } from "react";
import {
  ShieldCheck, CheckCircle2, Gavel, Lock, Activity,
  XCircle, AlertTriangle, ChevronDown, Loader2,
} from "lucide-react";

export const Route = createFileRoute("/governance")({ component: GovernancePage });

function GovernancePage() {
  const [pipelines, setPipelines] = useState<string[]>([]);
  const [pipeline,  setPipeline]  = useState("");
  const [data,      setData]      = useState<any>(null);
  const [loading,   setLoading]   = useState(false);

  useEffect(() => {
    fetch("/pipelines").then(r => r.json()).then(({ pipelines: pl }) => setPipelines(pl));
  }, []);

  useEffect(() => {
    if (!pipeline) return;
    setLoading(true); setData(null);
    fetch(`/deployment/${encodeURIComponent(pipeline)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [pipeline]);

  const gov       = data?.governance?.governance;
  const artifacts = data?.artifact_checks;
  const score     = gov?.readiness_score ?? data?.readiness_score ?? null;
  const state     = gov?.state as string | undefined;

  const bannerCls = !state
    ? "border-border bg-surface-2 text-foreground"
    : state === "APPROVED"
      ? "border-green-300 bg-green-50 text-green-800"
      : state === "CONDITIONAL"
        ? "border-yellow-300 bg-yellow-50 text-yellow-800"
        : "border-red-300 bg-red-50 text-red-800";

  const scoreCls = !state ? "text-foreground" :
    state === "APPROVED" ? "text-green-800" :
    state === "CONDITIONAL" ? "text-yellow-700" : "text-red-800";

  const stateTone: "success" | "warning" | "danger" | "neutral" =
    state === "APPROVED" ? "success" : state === "CONDITIONAL" ? "warning" : state ? "danger" : "neutral";

  const iconEl = !state ? null :
    state === "APPROVED" ? <ShieldCheck className="h-14 w-14 shrink-0 text-green-600" /> :
    state === "CONDITIONAL" ? <AlertTriangle className="h-14 w-14 shrink-0 text-yellow-600" /> :
    <XCircle className="h-14 w-14 shrink-0 text-red-600" />;

  // Build checks from real artifact data
  const checks: { label: string; description: string; passed: boolean }[] = [];
  if (artifacts) {
    Object.entries(artifacts.file_checks ?? {}).forEach(([file, c]: [string, any]) => {
      checks.push({ label: file, description: c.detail, passed: c.status === "PASSED" });
    });
    if (artifacts.dag_check) {
      checks.push({ label: "DAG Validation", description: artifacts.dag_check.detail, passed: artifacts.dag_check.status === "PASSED" });
    }
    if (artifacts.reconciliation_check) {
      checks.push({ label: "Reconciliation Parity", description: artifacts.reconciliation_check.detail, passed: artifacts.reconciliation_check.status === "PASSED" });
    }
    if (gov?.smoke_passed !== undefined) {
      checks.push({
        label: "Smoke Tests",
        description: `${gov.smoke_passed}/${gov.smoke_total} assertions passed`,
        passed: gov.smoke_passed === gov.smoke_total,
      });
    }
  }
  const passed = checks.filter(c => c.passed).length;

  return (
    <AppShell>
      <div className="h-full overflow-y-auto bg-background">

        {/* Page header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4">
          <Gavel className="h-5 w-5 text-muted-foreground" />
          <div>
            <div className="text-[12px] uppercase tracking-[0.14em] text-muted-foreground font-mono">Policy Approval &amp; Compliance</div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5">Migration Governance</h1>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {state && <Badge tone={stateTone}><ShieldCheck className="h-3.5 w-3.5" />{state}</Badge>}

            {/* Pipeline selector */}
            <div className="relative">
              <select
                value={pipeline}
                onChange={e => setPipeline(e.target.value)}
                className="h-9 pl-3 pr-8 rounded-md border border-border bg-white text-[13px] font-mono appearance-none focus:outline-none focus:border-primary/60 cursor-pointer"
              >
                <option value="">Select pipeline…</option>
                {pipelines.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            </div>
          </div>
        </div>

        <div className="p-6 space-y-6">

          {/* No pipeline selected */}
          {!pipeline && (
            <div className="rounded-xl border border-border bg-surface-2 p-12 text-center text-muted-foreground">
              <Gavel className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p className="text-[15px] font-medium">Select a pipeline to view its governance report</p>
              <p className="text-[13px] mt-1">Governance data is generated after a pipeline run completes.</p>
            </div>
          )}

          {/* Loading */}
          {pipeline && loading && (
            <div className="rounded-xl border border-border bg-surface-2 p-12 text-center text-muted-foreground">
              <Loader2 className="h-8 w-8 mx-auto mb-3 animate-spin opacity-40" />
              <p className="text-[14px]">Loading governance report…</p>
            </div>
          )}

          {/* No data yet */}
          {pipeline && !loading && !data && (
            <div className="rounded-xl border border-border bg-surface-2 p-12 text-center text-muted-foreground">
              <AlertTriangle className="h-8 w-8 mx-auto mb-3 opacity-30" />
              <p className="text-[15px] font-medium">No deployment data yet for <span className="font-mono text-foreground">{pipeline}</span></p>
              <p className="text-[13px] mt-1">Run the pipeline first, then check back here.</p>
            </div>
          )}

          {/* Governance verdict banner */}
          {data && gov && (
            <>
              <div className={`rounded-xl border-2 shadow-sm p-6 ${bannerCls}`}>
                <div className="flex items-center gap-5">
                  {iconEl}
                  <div className="flex-1">
                    <div className={`text-[12px] uppercase tracking-widest font-mono opacity-60`}>
                      Governance Verdict · {gov.approver ?? "SUPERVISOR"}
                    </div>
                    <div className={`text-[32px] font-bold leading-tight mt-0.5 ${scoreCls}`}>{state}</div>
                    <div className="text-[14px] opacity-75 mt-0.5">{gov.label}</div>
                  </div>
                  {score !== null && (
                    <div className="text-right shrink-0">
                      <div className={`text-[12px] font-mono uppercase tracking-wider opacity-60`}>Readiness Score</div>
                      <div className={`text-[52px] font-bold leading-none mt-1 ${scoreCls}`}>
                        {score}<span className="text-[30px]">/100</span>
                      </div>
                    </div>
                  )}
                </div>
                <div className={`mt-5 pt-4 border-t border-current/20 grid grid-cols-3 gap-4 text-[13px] font-mono opacity-80`}>
                  <div>
                    <span className="uppercase tracking-wider text-[11px] opacity-60">Pipeline</span>
                    <div className="mt-0.5 font-semibold">{pipeline}</div>
                  </div>
                  <div>
                    <span className="uppercase tracking-wider text-[11px] opacity-60">Risk Level</span>
                    <div className="mt-0.5 font-semibold">{gov.migration_risk ?? "—"}</div>
                  </div>
                  <div>
                    <span className="uppercase tracking-wider text-[11px] opacity-60">Policy</span>
                    <div className="mt-0.5 font-semibold">{gov.policy_version ?? "—"} · {gov.environment ?? "—"}</div>
                  </div>
                </div>
              </div>

              {/* Conditions (if any) */}
              {gov.conditions?.length > 0 && (
                <Panel eyebrow="Conditions to Resolve" title="Required before deployment">
                  <ul className="divide-y divide-border">
                    {gov.conditions.map((c: string, i: number) => (
                      <li key={i} className="flex items-start gap-3 px-6 py-3.5">
                        <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" />
                        <span className="text-[13px] text-foreground/80">{c}</span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              )}

              {/* Artifact checks */}
              {checks.length > 0 && (
                <Panel eyebrow="Policy Verification" title={`Governance Gate Checks — ${passed}/${checks.length} passed`}>
                  <ul className="divide-y divide-border">
                    {checks.map((check) => (
                      <li key={check.label} className="flex items-center gap-4 px-6 py-4 hover:bg-surface-2/40 transition-colors">
                        {check.passed
                          ? <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                          : <XCircle className="h-4 w-4 text-red-400 shrink-0" />}
                        <div className="flex-1 min-w-0">
                          <div className="text-[14px] font-medium font-mono">{check.label}</div>
                          <div className="text-[12px] text-muted-foreground mt-0.5">{check.description}</div>
                        </div>
                        <Badge tone={check.passed ? "success" : "danger"}>
                          {check.passed ? <><CheckCircle2 className="h-3 w-3" />PASSED</> : <><XCircle className="h-3 w-3" />FAILED</>}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                  <div className="px-6 py-3 border-t border-border bg-surface-2/30 flex items-center gap-2">
                    <span className="text-[12px] font-mono text-muted-foreground uppercase tracking-wider">
                      {passed} of {checks.length} gates cleared
                    </span>
                    <div className={`ml-auto flex items-center gap-1.5 text-[12px] font-mono ${passed === checks.length ? "text-green-600" : "text-warning"}`}>
                      <span className={`h-2 w-2 rounded-full ${passed === checks.length ? "bg-green-500" : "bg-warning"}`} />
                      {passed === checks.length ? "All checks passing" : `${checks.length - passed} check${checks.length - passed > 1 ? "s" : ""} failing`}
                    </div>
                  </div>
                </Panel>
              )}

              {/* Key metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { k: "Readiness Score",   v: score !== null ? `${score}/100` : "—" },
                  { k: "Migration Risk",    v: gov.migration_risk ?? "—" },
                  { k: "Smoke Tests",       v: gov.smoke_passed !== undefined ? `${gov.smoke_passed}/${gov.smoke_total}` : "—" },
                  { k: "Reconciliation",    v: artifacts?.reconciliation_check ? `${Math.round((artifacts.reconciliation_check.confidence ?? 0) * 100)}%` : "—" },
                ].map(({ k, v }) => (
                  <div key={k} className="rounded-lg border border-border bg-white px-4 py-3 shadow-sm">
                    <dt className="text-[11px] uppercase tracking-wider text-muted-foreground font-mono">{k}</dt>
                    <dd className="text-[18px] font-semibold mt-0.5">{v}</dd>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
