import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel, Badge } from "@/components/AppShell";
import { useEffect, useState } from "react";
import { FileCode2, ChevronDown } from "lucide-react";
import { onReset } from "@/lib/reset-store";

export const Route = createFileRoute("/workbench")({ component: Workbench });

function Workbench() {
  const [pipelines, setPipelines]   = useState<string[]>([]);
  const [pipeline, setPipeline]     = useState("");
  const [conversion, setConversion] = useState<any>(null);
  const [activeFile, setActiveFile] = useState<any>(null);
  const [showDag, setShowDag]       = useState(false);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");

  useEffect(() => {
    fetch("/pipelines")
      .then((r) => r.json())
      .then(({ pipelines: pl }) => {
        setPipelines(pl);
        if (pl.length) setPipeline(pl[0]);
      });
  }, []);

  // Listen for global reset
  useEffect(() => onReset(() => {
    setConversion(null);
    setActiveFile(null);
    setError("");
  }), []);

  useEffect(() => {
    if (!pipeline) return;
    setLoading(true);
    setError("");
    setConversion(null);
    setActiveFile(null);
    fetch(`/conversion/${encodeURIComponent(pipeline)}`)
      .then((r) => {
        if (!r.ok) throw new Error("No conversion data yet");
        return r.json();
      })
      .then((d) => {
        setConversion(d);
        if (d.files?.length) setActiveFile(d.files[0]);
        setShowDag(false);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [pipeline]);

  return (
    <AppShell>
      <div className="h-full overflow-y-auto bg-background">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4">
          <div>
            <div className="text-[13px] uppercase tracking-widest text-muted-foreground font-mono">Code Conversion Workbench</div>
            <h1 className="text-xl font-semibold tracking-tight mt-0.5">HiveQL → PySpark</h1>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {/* Pipeline selector */}
            <div className="relative">
              <select
                value={pipeline}
                onChange={(e) => setPipeline(e.target.value)}
                className="h-10 pl-4 pr-9 rounded-lg border border-border bg-white text-[14px] appearance-none cursor-pointer focus:outline-none focus:border-primary"
              >
                {pipelines.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            </div>
            {conversion && (
              <Badge tone="success">
                {conversion.files?.length} files · {conversion.transformations_applied} lines
              </Badge>
            )}
          </div>
        </div>

        {loading && (
          <div className="p-12 text-center text-[15px] text-muted-foreground">Loading conversion data…</div>
        )}

        {!loading && error && (
          <div className="p-12 text-center">
            <p className="text-[16px] text-muted-foreground">{error}</p>
            <p className="text-[14px] text-muted-foreground mt-2">Run the pipeline from the Dashboard first, then come back here.</p>
          </div>
        )}

        {!loading && conversion && (
          <div className="p-6 space-y-5">
            {/* File tabs */}
            <div className="flex items-center gap-2 flex-wrap">
              {conversion.files?.map((f: any) => (
                <button
                  key={f.filename}
                  onClick={() => { setActiveFile(f); setShowDag(false); }}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-[14px] font-mono transition ${
                    activeFile?.filename === f.filename && !showDag
                      ? "bg-primary text-white border-primary"
                      : "bg-white border-border text-foreground hover:border-primary/50"
                  }`}
                >
                  <FileCode2 className="h-4 w-4" />
                  {f.filename}
                  <span className="text-[12px] opacity-70">{f.transformations_applied} lines</span>
                </button>
              ))}
              {conversion.dag && (
                <button
                  onClick={() => { setShowDag(true); setActiveFile(null); }}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-[14px] font-mono transition ${
                    showDag
                      ? "bg-agent-supervisor/10 text-agent-supervisor border-agent-supervisor/30"
                      : "bg-white border-border text-foreground hover:border-primary/50"
                  }`}
                >
                  🗂 {conversion.dag_filename}
                </button>
              )}
            </div>

            {/* Diff view — two panes */}
            {activeFile && !showDag && (
              <div className="grid grid-cols-2 gap-4">
                <CodePane
                  title={`Source — ${activeFile.filename}`}
                  code={activeFile.source_hql}
                  lang="hive"
                />
                <CodePane
                  title={`Generated — ${activeFile.python_filename}`}
                  code={activeFile.spark_python}
                  lang="python"
                />
              </div>
            )}

            {/* DAG view */}
            {showDag && (
              <div className="grid grid-cols-1 gap-4">
                <CodePane
                  title={`MWAA DAG — ${conversion.dag_filename}`}
                  code={conversion.dag}
                  lang="python"
                />
              </div>
            )}

            {/* Stats */}
            {activeFile && !showDag && (
              <div className="grid grid-cols-3 gap-4">
                <Stat label="Transformations applied" value={String(activeFile.transformations_applied)} />
                <Stat label="Source language"         value={conversion.source_language || "HiveQL"} />
                <Stat label="Target language"         value={conversion.target_language || "PySpark"} />
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}

function CodePane({ title, code, lang }: { title: string; code: string; lang: "hive" | "python" }) {
  return (
    <Panel title={title}>
      <div className="overflow-auto max-h-[600px]">
        <pre className="p-5 text-[13.5px] leading-[1.7] font-mono text-foreground/90">
          {code?.split("\n").map((line, i) => (
            <div key={i} className="flex gap-4 group hover:bg-surface-2/50 rounded">
              <span className="text-muted-foreground/40 select-none w-8 text-right shrink-0 text-[12px] pt-px">{i + 1}</span>
              <span className="flex-1 whitespace-pre">{line}</span>
            </div>
          ))}
        </pre>
      </div>
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-white p-5 shadow-sm">
      <div className="text-[13px] uppercase tracking-wider text-muted-foreground font-mono">{label}</div>
      <div className="text-[20px] font-semibold mt-2">{value}</div>
    </div>
  );
}
