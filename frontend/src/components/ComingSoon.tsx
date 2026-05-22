import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel, Badge } from "@/components/AppShell";
import { ReactNode } from "react";
import { Network, Gavel, Rocket, ScrollText } from "lucide-react";

function ComingSoon({ icon, title, blurb }: { icon: ReactNode; title: string; blurb: string }) {
  return (
    <AppShell>
      <div className="h-full overflow-y-auto">
        <div className="px-6 py-4 border-b border-border">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground font-mono">Platform · Roadmap</div>
          <h1 className="text-lg font-semibold tracking-tight mt-0.5">{title}</h1>
        </div>
        <div className="p-6">
          <Panel>
            <div className="p-10 flex flex-col items-center text-center bg-grid">
              <div className="h-12 w-12 rounded-md bg-surface-2 border border-border-strong flex items-center justify-center mb-4">
                {icon}
              </div>
              <Badge tone="info">Coming Soon</Badge>
              <h2 className="text-xl font-semibold tracking-tight mt-3">{title}</h2>
              <p className="text-sm text-muted-foreground mt-2 max-w-md">{blurb}</p>
              <div className="mt-5 text-[11px] font-mono text-muted-foreground/80">
                roadmap · 2026-Q3 · tracked in JIRA · HARNESS-{Math.floor(Math.random() * 999) + 100}
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}

export const graphRoute = {
  path: "/context-graph",
  Component: () => <ComingSoon icon={<Network className="h-5 w-5 text-info" />} title="Context Graph" blurb="Live lineage and dependency graph backed by neo4j_mcp. Inspect upstream consumers, downstream blast radius, and inferred semantic links." />,
};
export const govRoute = {
  path: "/governance",
  Component: () => <ComingSoon icon={<Gavel className="h-5 w-5 text-warning" />} title="Governance" blurb="Policy decisions, hook traces, and audit-grade approvals across every supervised action. Drill into rationale per agent step." />,
};
export const deployRoute = {
  path: "/deployments",
  Component: () => <ComingSoon icon={<Rocket className="h-5 w-5 text-success" />} title="Deployments" blurb="MWAA rollouts, EMR Serverless promotions, canary states, and rollback controls across environments." />,
};
export const auditRoute = {
  path: "/audit",
  Component: () => <ComingSoon icon={<ScrollText className="h-5 w-5 text-muted-foreground" />} title="Audit Logs" blurb="Immutable orchestration ledger — every supervisor decision, hook outcome, MCP call, and operator action preserved for compliance." />,
};

export { ComingSoon };
