import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/ComingSoon";
import { Network } from "lucide-react";
export const Route = createFileRoute("/context-graph")({
  component: () => <ComingSoon icon={<Network className="h-5 w-5 text-info" />} title="Context Graph" blurb="Live lineage and dependency graph backed by neo4j_mcp. Inspect upstream consumers, downstream blast radius, and inferred semantic links." />,
});
