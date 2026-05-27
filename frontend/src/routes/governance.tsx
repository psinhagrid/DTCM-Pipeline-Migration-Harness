import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel, Badge } from "@/components/AppShell";
import {
  ShieldCheck,
  CheckCircle2,
  Gavel,
  Lock,
  Database,
  Clock,
  Activity,
  ChevronRight,
} from "lucide-react";

export const Route = createFileRoute("/governance")({ component: GovernancePage });

// ── Demo data ─────────────────────────────────────────────────────────────────

const POLICY_CHECKS = [
  {
    label: "Schema Governance",
    description: "All output schemas registered in Glue catalog",
    icon: Database,
  },
  {
    label: "PII Classification",
    description: "No unmasked PII fields detected in target",
    icon: Lock,
  },
  {
    label: "SDS Compliance",
    description: "SDS tier validated against Visa security policy",
    icon: ShieldCheck,
  },
  {
    label: "KMS Encryption",
    description: "All S3 paths use approved KMS key ARNs",
    icon: Lock,
  },
  {
    label: "Row Count Parity",
    description: "Target row count within 0.1% of source",
    icon: Activity,
  },
  {
    label: "SLA Compliance",
    description: "Estimated runtime 4.2 min within 15-min SLA",
    icon: Clock,
  },
  {
    label: "Lineage Registration",
    description: "Pipeline lineage written to Neo4j graph",
    icon: ChevronRight,
  },
  {
    label: "Smoke Test",
    description: "3/3 smoke test assertions passed",
    icon: CheckCircle2,
  },
];

const STAT_CARDS = [
  {
    label: "Policy Checks",
    value: "8 / 8 Passed",
    tone: "success" as const,
    icon: CheckCircle2,
  },
  {
    label: "Risk Level",
    value: "LOW",
    tone: "info" as const,
    icon: ShieldCheck,
  },
  {
    label: "Data Compliance",
    value: "SDS / KMS / PII ✓",
    tone: "success" as const,
    icon: Lock,
  },
  {
    label: "Deployment Gate",
    value: "CLEARED",
    tone: "success" as const,
    icon: Gavel,
  },
];

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  tone,
  icon: Icon,
}: {
  label: string;
  value: string;
  tone: "success" | "info" | "warning" | "danger" | "neutral";
  icon: React.ElementType;
}) {
  const colorMap = {
    success: "text-green-600 bg-green-50 border-green-200",
    info: "text-blue-600 bg-blue-50 border-blue-200",
    warning: "text-yellow-600 bg-yellow-50 border-yellow-200",
    danger: "text-red-600 bg-red-50 border-red-200",
    neutral: "text-muted-foreground bg-surface-2 border-border",
  };
  const iconMap = {
    success: "text-green-500",
    info: "text-blue-500",
    warning: "text-yellow-500",
    danger: "text-red-500",
    neutral: "text-muted-foreground",
  };

  return (
    <div className={`rounded-xl border shadow-sm p-5 ${colorMap[tone]}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[12px] uppercase tracking-[0.14em] font-mono opacity-70 mb-1">
            {label}
          </div>
          <div className="text-[18px] font-bold tracking-tight">{value}</div>
        </div>
        <Icon className={`h-5 w-5 shrink-0 mt-0.5 ${iconMap[tone]}`} />
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function GovernancePage() {
  return (
    <AppShell>
      <div className="h-full overflow-y-auto bg-background">

        {/* Page header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4">
          <Gavel className="h-5 w-5 text-muted-foreground" />
          <div>
            <div className="text-[12px] uppercase tracking-[0.14em] text-muted-foreground font-mono">
              Policy Approval &amp; Compliance
            </div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5">
              Migration Governance
            </h1>
          </div>
          <div className="ml-auto">
            <Badge tone="success">
              <ShieldCheck className="h-3.5 w-3.5" />
              APPROVED
            </Badge>
          </div>
        </div>

        <div className="p-6 space-y-6">

          {/* PASS banner */}
          <div className="rounded-xl border-2 border-green-300 bg-green-50 shadow-sm p-6">
            <div className="flex items-center gap-5">
              <ShieldCheck className="h-14 w-14 shrink-0 text-green-600" />
              <div className="flex-1">
                <div className="text-[12px] uppercase tracking-widest font-mono text-green-700/60">
                  Governance Verdict · DTCM Supervisor Agent
                </div>
                <div className="text-[32px] font-bold text-green-800 leading-tight mt-0.5">
                  PASS
                </div>
                <div className="text-[15px] text-green-700/80 mt-0.5">
                  Status: APPROVED · Approved at: 2026-05-27 · 11:42 UTC
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-[12px] font-mono text-green-700/60 uppercase tracking-wider">
                  Governance Score
                </div>
                <div className="text-[52px] font-bold leading-none mt-1 text-green-800">
                  94<span className="text-[30px]">/100</span>
                </div>
              </div>
            </div>
            <div className="mt-5 pt-4 border-t border-green-300/60 grid grid-cols-3 gap-4 text-[13px] font-mono text-green-700/80">
              <div>
                <span className="uppercase tracking-wider text-[11px] text-green-600/60">Approved by</span>
                <div className="mt-0.5 font-semibold">DTCM Supervisor Agent</div>
              </div>
              <div>
                <span className="uppercase tracking-wider text-[11px] text-green-600/60">Pipeline</span>
                <div className="mt-0.5 font-semibold">silver_orders</div>
              </div>
              <div>
                <span className="uppercase tracking-wider text-[11px] text-green-600/60">Wave</span>
                <div className="mt-0.5 font-semibold">wave-1 · AWS MWAA + EMR Iceberg</div>
              </div>
            </div>
          </div>

          {/* 4 stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {STAT_CARDS.map((card) => (
              <StatCard key={card.label} {...card} />
            ))}
          </div>

          {/* Policy checks table */}
          <Panel eyebrow="Policy Verification" title="Governance Gate Checks">
            <ul className="divide-y divide-border">
              {POLICY_CHECKS.map((check) => {
                const Icon = check.icon;
                return (
                  <li
                    key={check.label}
                    className="flex items-center gap-4 px-6 py-4 hover:bg-surface-2/40 transition-colors"
                  >
                    <Icon className="h-4.5 w-4.5 text-green-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-[15px] font-medium">{check.label}</div>
                      <div className="text-[13px] text-muted-foreground mt-0.5">
                        {check.description}
                      </div>
                    </div>
                    <Badge tone="success">
                      <CheckCircle2 className="h-3 w-3" />
                      PASSED
                    </Badge>
                  </li>
                );
              })}
            </ul>
            <div className="px-6 py-3 border-t border-border bg-surface-2/30 flex items-center gap-2">
              <span className="text-[12px] font-mono text-muted-foreground uppercase tracking-wider">
                8 of 8 gates cleared
              </span>
              <div className="ml-auto flex items-center gap-1.5 text-[12px] font-mono text-green-600">
                <span className="h-2 w-2 rounded-full bg-green-500" />
                All checks passing
              </div>
            </div>
          </Panel>

          {/* Rationale section */}
          <Panel eyebrow="Approval Rationale" title="Supervisor Decision Rationale">
            <div className="p-5 space-y-3">
              <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                  <p className="text-[14px] text-green-800 leading-relaxed">
                    Pipeline <span className="font-semibold font-mono">silver_orders</span> passed
                    all 8 governance gates. Complexity tier:{" "}
                    <span className="font-semibold">MODERATE</span>. No CRITICAL or HIGH severity
                    issues detected. Semantic similarity: <span className="font-semibold">89%</span>.
                    Row variance: <span className="font-semibold">0.0%</span>. Approved for
                    wave-1 deployment to AWS MWAA + EMR Iceberg.
                  </p>
                </div>
              </div>

              <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-1">
                {[
                  { k: "Complexity Tier",    v: "MODERATE" },
                  { k: "Semantic Similarity", v: "89%" },
                  { k: "Row Variance",       v: "0.0%" },
                  { k: "Estimated Runtime",  v: "4.2 min" },
                ].map(({ k, v }) => (
                  <div key={k} className="rounded-lg border border-border bg-white px-4 py-3">
                    <dt className="text-[11px] uppercase tracking-wider text-muted-foreground font-mono">
                      {k}
                    </dt>
                    <dd className="text-[16px] font-semibold mt-0.5">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </Panel>

        </div>
      </div>
    </AppShell>
  );
}
