import { Link, useRouterState } from "@tanstack/react-router";
import { ReactNode } from "react";
import {
  LayoutDashboard,
  Terminal,
  Code2,
  ShieldCheck,
  Network,
  Gavel,
  Rocket,
  ScrollText,
  Activity,
  Search,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navMain = [
  { to: "/",              label: "Executive",   icon: LayoutDashboard },
  { to: "/orchestration", label: "Logs",        icon: Terminal },
  { to: "/workbench",     label: "Workbench",   icon: Code2 },
  { to: "/validation",    label: "Validation",  icon: ShieldCheck },
  { to: "/deployments",   label: "Deployments", icon: Rocket },
  { to: "/skills",        label: "Skills",      icon: BookOpen },
];

const navFuture = [
  { to: "/context-graph", label: "Context Graph", icon: Network },
  { to: "/governance",    label: "Governance",    icon: Gavel },
  { to: "/audit",         label: "Audit Logs",    icon: ScrollText },
];

function NavItem({ to, label, icon: Icon, active }: { to: string; label: string; icon: any; active: boolean }) {
  return (
    <Link
      to={to}
      className={cn(
        "group flex items-center gap-3 rounded-md px-3 py-2.5 text-[15px] transition-colors",
        active
          ? "bg-primary/10 text-primary border border-primary/25 font-medium"
          : "text-foreground/70 hover:text-foreground hover:bg-surface-2 border border-transparent",
      )}
    >
      <Icon className={cn("h-4.5 w-4.5", active ? "text-primary" : "text-foreground/50 group-hover:text-foreground")} />
      <span className="tracking-tight">{label}</span>
      {active && <span className="ml-auto h-2 w-2 rounded-full bg-primary pulse-dot" />}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="h-screen flex bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-border bg-white shadow-sm flex flex-col">
        <div className="px-5 py-5 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="relative h-9 w-9 rounded-md bg-primary/10 border border-primary/30 flex items-center justify-center">
              <div className="h-2 w-2 rounded-full bg-primary pulse-dot" />
            </div>
            <div>
              <div className="text-[15px] font-semibold tracking-tight leading-none text-foreground">DTCM Harness</div>
              <div className="text-[12px] text-muted-foreground mt-1 font-mono uppercase tracking-wider">Migration · Control Plane</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          <div className="px-2 pb-2 text-[12px] uppercase tracking-[0.14em] text-muted-foreground font-mono">Operations</div>
          {navMain.map((n) => (
            <NavItem key={n.to} {...n} active={path === n.to} />
          ))}

          <div className="px-2 pt-5 pb-2 text-[12px] uppercase tracking-[0.14em] text-muted-foreground font-mono">Platform · Soon</div>
          {navFuture.map((n) => (
            <NavItem key={n.to} {...n} active={path === n.to} />
          ))}
        </nav>

        <div className="m-3 rounded-md border border-border bg-surface-2 p-3">
          <div className="flex items-center gap-2 text-[13px] text-muted-foreground font-mono">
            <span className="h-2 w-2 rounded-full bg-success pulse-dot" />
            supervisor.online
          </div>
          <div className="mt-1.5 text-[12px] text-muted-foreground/80 font-mono leading-relaxed">
            cluster: us-east-1<br />build: 2026.05.22-rc3
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col bg-background">
        <TopBar />
        <main className="flex-1 min-w-0 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}

function TopBar() {
  return (
    <header className="h-14 border-b border-border bg-white shadow-sm flex items-center px-5 gap-4">
      <div className="flex items-center gap-2 text-[13px] font-mono text-muted-foreground">
        <span className="h-2 w-2 rounded-full bg-success pulse-dot" />
        <span className="text-foreground font-medium">SUPERVISOR · ONLINE</span>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <div className="relative w-72 hidden md:block">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            placeholder="Search pipelines, agents, artifacts…"
            className="w-full h-9 pl-9 pr-10 rounded-md bg-surface-2 border border-border text-[14px] placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/60"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[12px] text-muted-foreground font-mono">⌘K</kbd>
        </div>

        <div className="flex items-center gap-2 text-[13px] font-mono text-muted-foreground">
          <Activity className="h-4 w-4 text-info" />
          <span>active</span>
        </div>

        <div className="h-8 w-8 rounded-full bg-primary/15 border border-primary/30 flex items-center justify-center text-[13px] font-semibold text-primary">
          DT
        </div>
      </div>
    </header>
  );
}

export function Panel({
  title, eyebrow, action, children, className,
}: { title?: string; eyebrow?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-lg border border-border bg-white shadow-sm", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div>
            {eyebrow && <div className="text-[12px] uppercase tracking-[0.14em] text-muted-foreground font-mono">{eyebrow}</div>}
            {title && <h3 className="text-[15px] font-semibold tracking-tight mt-0.5">{title}</h3>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatusDot({ status }: { status: string }) {
  const cls =
    status === "succeeded" ? "bg-success" :
    status === "running"   ? "bg-info pulse-dot" :
    status === "validating"? "bg-info pulse-dot" :
    status === "failed"    ? "bg-danger" :
    status === "paused"    ? "bg-warning" :
    "bg-muted-foreground";
  return <span className={cn("inline-block h-2 w-2 rounded-full", cls)} />;
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "success" | "warning" | "danger" | "info"; children: ReactNode }) {
  const toneCls = {
    neutral: "text-muted-foreground border-border bg-surface-2",
    success: "text-success border-success/30 bg-success/10",
    warning: "text-warning border-warning/30 bg-warning/10",
    danger:  "text-danger border-danger/30 bg-danger/10",
    info:    "text-info border-info/30 bg-info/10",
  }[tone];
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-1 rounded text-[12px] font-mono uppercase tracking-wider border font-medium", toneCls)}>
      {children}
    </span>
  );
}
