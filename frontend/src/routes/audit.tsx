import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/ComingSoon";
import { ScrollText } from "lucide-react";
export const Route = createFileRoute("/audit")({
  component: () => <ComingSoon icon={<ScrollText className="h-5 w-5 text-muted-foreground" />} title="Audit Logs" blurb="Immutable orchestration ledger — every supervisor decision, hook outcome, MCP call, and operator action preserved for compliance." />,
});
