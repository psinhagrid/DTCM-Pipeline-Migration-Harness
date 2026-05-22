import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/ComingSoon";
import { Gavel } from "lucide-react";
export const Route = createFileRoute("/governance")({
  component: () => <ComingSoon icon={<Gavel className="h-5 w-5 text-warning" />} title="Governance" blurb="Policy decisions, hook traces, and audit-grade approvals across every supervised action. Drill into rationale per agent step." />,
});
