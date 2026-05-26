import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel, Badge } from "@/components/AppShell";
import React, { useEffect, useState } from "react";
import {
  ChevronDown, CheckCircle2, XCircle, AlertCircle,
  Rocket, ShieldCheck, ShieldAlert, ShieldX, FileJson,
} from "lucide-react";
import { onReset } from "@/lib/reset-store";
import { Copy, Check } from "lucide-react";

export const Route = createFileRoute("/deployments")({ component: Deployments });

// ── Config ────────────────────────────────────────────────────────────────────

const GOV_CONFIG: Record<string, { color: string; bg: string; border: string; icon: any }> = {
  APPROVED:          { color: "text-green-800",  bg: "bg-green-50",  border: "border-green-300",  icon: ShieldCheck },
  APPROVED_NON_PROD: { color: "text-blue-800",   bg: "bg-blue-50",   border: "border-blue-300",   icon: ShieldAlert },
  CONDITIONAL:       { color: "text-yellow-800", bg: "bg-yellow-50", border: "border-yellow-300", icon: ShieldAlert },
  BLOCKED:           { color: "text-red-800",    bg: "bg-red-50",    border: "border-red-300",    icon: ShieldX     },
};

function tone(s: string): "success"|"warning"|"danger"|"neutral" {
  if (["PASSED","APPROVED","APPROVED_NON_PROD"].includes(s)) return "success";
  if (["WARNING","CONDITIONAL"].includes(s)) return "warning";
  if (["FAILED","BLOCKED"].includes(s))      return "danger";
  return "neutral";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "PASSED")  return <CheckCircle2 className="h-5 w-5 text-green-600" />;
  if (status === "FAILED")  return <XCircle      className="h-5 w-5 text-red-600"   />;
  if (status === "WARNING") return <AlertCircle  className="h-5 w-5 text-yellow-500"/>;
  return <div className="h-5 w-5 rounded-full border-2 border-gray-200 bg-gray-50" />;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function GovernanceBanner({ gov }: { gov: any }) {
  const cfg  = GOV_CONFIG[gov?.state] || GOV_CONFIG.BLOCKED;
  const Icon = cfg.icon;
  return (
    <div className={`rounded-xl border-2 p-6 ${cfg.bg} ${cfg.border}`}>
      <div className="flex items-center gap-5">
        <Icon className={`h-12 w-12 shrink-0 ${cfg.color}`} />
        <div className="flex-1">
          <div className={`text-[12px] uppercase tracking-widest font-mono ${cfg.color} opacity-60`}>
            Governance Decision · {gov?.policy_version} · {gov?.approver}
          </div>
          <div className={`text-[24px] font-bold mt-1 ${cfg.color}`}>{gov?.state}</div>
          <div className={`text-[15px] mt-0.5 ${cfg.color} opacity-80`}>{gov?.label}</div>
        </div>
        <div className="text-right shrink-0">
          <div className={`text-[12px] font-mono ${cfg.color} opacity-60`}>Readiness</div>
          <div className={`text-[48px] font-bold leading-none mt-1 ${cfg.color}`}>
            {gov?.readiness_score ?? "—"}<span className="text-[28px]">%</span>
          </div>
        </div>
      </div>
      {gov?.conditions?.length > 0 && (
        <div className={`mt-5 pt-4 border-t border-current/20`}>
          <div className={`text-[12px] uppercase tracking-wider font-mono ${cfg.color} opacity-60 mb-2`}>Conditions</div>
          <ul className="space-y-1.5">
            {gov.conditions.map((c: string, i: number) => (
              <li key={i} className={`flex items-start gap-2 text-[14px] ${cfg.color}`}>
                <span className="mt-0.5 shrink-0 font-bold">→</span>{c}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Timeline({ data }: { data: any }) {
  const artOk   = data.artifact_checks?.deployment_ready ?? data.artifact_checks?.all_artifacts_valid;
  const smokeOk = (data.smoke_results?.overall ?? data.smoke_results?.status) !== "FAILED";
  const govOk   = ["APPROVED","APPROVED_NON_PROD"].includes(data.deployment_status ?? data.governance?.state);

  const stages = [
    { label: "Artifact Validation",  sub: "Python AST + DAG structure",   ok: artOk  },
    { label: "Bundle Packaging",     sub: "Archive + SHA256 signature",    ok: true   },
    { label: "CI/CD Generation",     sub: "Deployment YAML + pipeline cfg",ok: true   },
    { label: "Non-prod Deployment",  sub: "MWAA register + EMR validate",  ok: true   },
    { label: "Smoke Test Suite",     sub: `${data.smoke_results?.passed}/${data.smoke_results?.total} tests`, ok: smokeOk },
    { label: "Governance Approval",  sub: data.governance?.state,          ok: govOk  },
  ];

  return (
    <div className="p-5">
      <div className="relative">
        <div className="absolute left-4 top-5 bottom-5 w-0.5 bg-gray-200" />
        <div className="space-y-5">
          {stages.map((s, i) => (
            <div key={i} className="flex items-center gap-4 relative">
              <div className={`h-9 w-9 rounded-full flex items-center justify-center shrink-0 z-10 border-2 ${
                s.ok ? "bg-green-50 border-green-400" : "bg-red-50 border-red-300"
              }`}>
                {s.ok ? <CheckCircle2 className="h-5 w-5 text-green-600" />
                       : <XCircle      className="h-5 w-5 text-red-500" /> }
              </div>
              <div className="flex-1">
                <div className="text-[15px] font-semibold">{s.label}</div>
                <div className="text-[12px] text-muted-foreground font-mono">{s.sub}</div>
              </div>
              <Badge tone={s.ok ? "success" : "danger"}>{s.ok ? "DONE" : "FAILED"}</Badge>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SmokeTests({ results }: { results: any }) {
  return (
    <ul className="divide-y divide-border">
      {(results?.tests || []).map((t: any, i: number) => (
        <li key={i} className="flex items-center gap-4 px-5 py-4 hover:bg-surface-2/40">
          <StatusIcon status={t.status} />
          <div className="flex-1 min-w-0">
            <div className="text-[15px] font-medium">{t.name}</div>
            <div className="text-[13px] text-muted-foreground truncate">{t.detail}</div>
            {t.note && <div className="text-[12px] text-blue-500 font-mono mt-0.5">{t.note}</div>}
          </div>
          <span className={`text-[11px] font-mono px-2 py-0.5 rounded border ${
            t.type === "real"
              ? "text-green-700 bg-green-50 border-green-200"
              : "text-blue-700 bg-blue-50 border-blue-200"
          }`}>{t.type}</span>
          <span className="text-[12px] font-mono text-muted-foreground shrink-0 w-16 text-right">{t.runtime}</span>
          <Badge tone={tone(t.status)}>{t.status}</Badge>
        </li>
      ))}
    </ul>
  );
}

function ArtifactChecks({ checks }: { checks: any }) {
  const files = Object.entries(checks?.file_checks || {});
  const rows  = [
    ...files.map(([fname, r]: [string, any]) => ({ label: fname, detail: r.detail, status: r.status })),
    checks?.dag_check    && { label: "DAG Structure",        detail: checks.dag_check.detail,    status: checks.dag_check.status    },
    checks?.reconciliation_check && { label: "Reconciliation Gate", detail: checks.reconciliation_check.detail, status: checks.reconciliation_check.status },
  ].filter(Boolean);

  return (
    <ul className="divide-y divide-border">
      {rows.map((r: any, i: number) => (
        <li key={i} className="flex items-center gap-4 px-5 py-4 hover:bg-surface-2/40">
          <StatusIcon status={r.status} />
          <div className="flex-1 min-w-0">
            <div className="text-[14px] font-mono font-medium">{r.label}</div>
            <div className="text-[13px] text-muted-foreground">{r.detail}</div>
          </div>
          <Badge tone={tone(r.status)}>{r.status}</Badge>
        </li>
      ))}
    </ul>
  );
}

function OutputFiles({ output }: { output: any }) {
  return (
    <div className="p-5 space-y-2">
      {(output?.files_written || []).map((f: string, i: number) => {
        const name = f.split("/").slice(-2).join("/");
        return (
          <div key={i} className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-surface-2 border border-border">
            <FileJson className="h-4 w-4 text-blue-500 shrink-0" />
            <span className="text-[13px] font-mono flex-1">{name}</span>
            <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
          </div>
        );
      })}
      <p className="text-[12px] text-muted-foreground font-mono pt-1 pl-1">
        → {output?.output_dir}
      </p>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

// ── JSON File Viewer ──────────────────────────────────────────────────────────

function FileViewer({ pipeline }: { pipeline: string }) {
  const [files,    setFiles]    = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [content,  setContent]  = useState<any>(null);
  const [copied,   setCopied]   = useState(false);

  useEffect(() => {
    if (!pipeline) return;
    fetch(`/output/${encodeURIComponent(pipeline)}`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (d?.files?.length) {
          setFiles(d.files);
          setSelected(d.files[0]);
        }
      }).catch(() => {});
  }, [pipeline]);

  useEffect(() => {
    if (!selected || !pipeline) return;
    setContent(null);
    fetch(`/output/${encodeURIComponent(pipeline)}/${encodeURIComponent(selected)}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setContent).catch(() => {});
  }, [selected, pipeline]);

  function copyJson() {
    if (!content) return;
    navigator.clipboard.writeText(JSON.stringify(content, null, 2)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  }

  if (!files.length) return null;

  return (
    <Panel eyebrow="Output Files · Written to disk" title="Deployment logs & reports">
      <div className="p-4 space-y-3">
        {/* File selector */}
        <div className="flex items-center gap-3">
          <span className="text-[13px] text-muted-foreground font-mono shrink-0">Select file:</span>
          <div className="flex gap-2 flex-wrap flex-1">
            {files.map((f) => (
              <button
                key={f}
                onClick={() => setSelected(f)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[13px] font-mono transition ${
                  selected === f
                    ? "bg-primary text-white border-primary"
                    : "bg-white border-border text-foreground hover:border-primary/50"
                }`}
              >
                <FileJson className="h-3.5 w-3.5" />
                {f}
              </button>
            ))}
          </div>
          <button
            onClick={copyJson}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg border border-border text-[13px] text-muted-foreground hover:text-foreground hover:bg-surface-2 transition shrink-0"
          >
            {copied ? <><Check className="h-3.5 w-3.5 text-green-500" /> Copied</> : <><Copy className="h-3.5 w-3.5" /> Copy</>}
          </button>
        </div>

        {/* JSON content */}
        {content ? (
          <div className="rounded-lg border border-border overflow-hidden">
            <div className="bg-gray-50 border-b border-border px-4 py-2 text-[12px] font-mono text-muted-foreground">
              output/{pipeline}/{selected}
            </div>
            <pre className="p-5 text-[13px] font-mono leading-relaxed overflow-x-auto max-h-[500px] overflow-y-auto bg-white">
              {colorJson(JSON.stringify(content, null, 2))}
            </pre>
          </div>
        ) : (
          <div className="p-6 text-center text-[14px] text-muted-foreground">Loading…</div>
        )}
      </div>
    </Panel>
  );
}

function colorJson(raw: string): React.ReactNode {
  const lines = raw.split("\n");
  return (
    <>
      {lines.map((line, i) => {
        const keyMatch  = line.match(/^(\s*)("[\w_]+")(\s*:\s*)(.*)/);
        const strMatch  = !keyMatch && line.match(/^(\s*)("[^"]*")(,?)$/);
        const numMatch  = !keyMatch && !strMatch && line.match(/^(\s*)(-?\d[\d.]*)(,?)$/);
        const boolMatch = !keyMatch && !strMatch && !numMatch && line.match(/^(\s*)(true|false|null)(,?)$/);

        if (keyMatch) {
          const valPart = keyMatch[4];
          const isStr  = valPart.startsWith('"');
          const isNum  = /^-?\d/.test(valPart);
          const isBool = /^(true|false|null)/.test(valPart);
          return (
            <div key={i}>
              {keyMatch[1]}
              <span style={{ color: "#16a34a" }}>{keyMatch[2]}</span>
              {keyMatch[3]}
              <span style={{ color: isStr ? "#b45309" : isNum ? "#7c3aed" : isBool ? "#0369a1" : undefined }}>{valPart}</span>
              {"\n"}
            </div>
          );
        }
        return <span key={i}>{line}{"\n"}</span>;
      })}
    </>
  );
}

function Deployments() {
  const [pipelines, setPipelines] = useState<string[]>([]);
  const [pipeline,  setPipeline]  = useState("");
  const [data,      setData]      = useState<any>(null);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState("");

  useEffect(() => {
    fetch("/pipelines").then((r) => r.json())
      .then(({ pipelines: pl }) => { setPipelines(pl); if (pl.length) setPipeline(pl[0]); });
  }, []);

  useEffect(() => {
    if (!pipeline) return;
    setLoading(true); setError(""); setData(null);
    fetch(`/deployment/${encodeURIComponent(pipeline)}`)
      .then((r) => { if (!r.ok) throw new Error("No deployment data yet — run full pipeline first"); return r.json(); })
      .then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [pipeline]);

  useEffect(() => onReset(() => { setData(null); setError(""); }), []);

  return (
    <AppShell>
      <div className="h-full overflow-y-auto bg-background">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4">
          <div>
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Deployment Orchestration</div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5 flex items-center gap-2">
              <Rocket className="h-5 w-5 text-primary" /> Migration Deployment
            </h1>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <div className="relative">
              <select value={pipeline} onChange={(e) => setPipeline(e.target.value)}
                className="h-10 pl-4 pr-9 rounded-lg border border-border bg-white text-[14px] appearance-none cursor-pointer focus:outline-none focus:border-primary">
                {pipelines.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            </div>
            {data && <Badge tone={tone(data.deployment_status)}>{data.deployment_status}</Badge>}
          </div>
        </div>

        {loading && <div className="p-12 text-center text-[15px] text-muted-foreground">Loading deployment data…</div>}

        {!loading && error && (
          <div className="p-12 text-center">
            <Rocket className="h-14 w-14 text-muted-foreground/20 mx-auto mb-4" />
            <p className="text-[16px] text-muted-foreground">{error}</p>
          </div>
        )}

        {!loading && data && (
          <div className="p-8 space-y-6">

            {/* 1 — Governance Banner */}
            <GovernanceBanner gov={data.governance} />

            {/* 2 — Timeline + Score */}
            <div className="grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-5">
                <Panel eyebrow="Deployment Lifecycle" title="Stage timeline">
                  <Timeline data={data} />
                </Panel>
              </div>

              <div className="col-span-12 lg:col-span-7 space-y-5">
                <Panel eyebrow="Readiness Score" title="Deployment readiness">
                  <div className="p-5">
                    <div className="flex items-baseline justify-between mb-3">
                      <span className="text-[48px] font-bold leading-none">
                        {data.governance?.readiness_score ?? 0}
                        <span className="text-[28px] text-muted-foreground">%</span>
                      </span>
                      <div className="text-right">
                        <div className="text-[13px] text-muted-foreground">Smoke tests</div>
                        <div className="text-[20px] font-semibold">
                          {data.smoke_results?.passed}/{data.smoke_results?.total} passed
                        </div>
                      </div>
                    </div>
                    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${
                        (data.governance?.readiness_score ?? 0) >= 88 ? "bg-green-500" :
                        (data.governance?.readiness_score ?? 0) >= 72 ? "bg-blue-500"  :
                        (data.governance?.readiness_score ?? 0) >= 55 ? "bg-yellow-500": "bg-red-500"
                      }`} style={{ width: `${data.governance?.readiness_score ?? 0}%` }} />
                    </div>
                    <div className="grid grid-cols-3 gap-4 mt-5">
                      {[
                        { label: "Confidence",     value: `${((data.governance?.confidence || 0) * 100).toFixed(0)}%` },
                        { label: "Migration Risk", value: data.governance?.migration_risk || "—" },
                        { label: "Environment",    value: data.governance?.environment || "—" },
                      ].map((m) => (
                        <div key={m.label} className="rounded-lg bg-surface-2 p-4 border border-border">
                          <div className="text-[11px] text-muted-foreground uppercase tracking-wider font-mono">{m.label}</div>
                          <div className="text-[16px] font-semibold mt-1">{m.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </Panel>

                <Panel eyebrow="Output · Written to disk" title="Generated manifests">
                  <OutputFiles output={data.output} />
                </Panel>
              </div>
            </div>

            {/* 3 — Smoke Tests */}
            <Panel eyebrow="Smoke Test Suite"
              title={`${data.smoke_results?.passed}/${data.smoke_results?.total} tests · score ${data.smoke_results?.score}%`}>
              <SmokeTests results={data.smoke_results} />
            </Panel>

            {/* 4 — Artifact Validation */}
            <Panel eyebrow="Artifact Validation" title="Generated file checks">
              <ArtifactChecks checks={data.artifact_checks} />
            </Panel>

            {/* 5 — JSON File Viewer */}
            <FileViewer pipeline={pipeline} />

          </div>
        )}
      </div>
    </AppShell>
  );
}
