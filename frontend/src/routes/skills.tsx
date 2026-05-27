import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/AppShell";
import { useEffect, useState, useRef } from "react";
import { BookOpen, Save, Cpu, FileText, Globe, Eye, Pencil } from "lucide-react";
import { marked } from "marked";
marked.setOptions({ breaks: true, gfm: true });

function stripFrontmatter(text: string): string {
  if (!text.startsWith("---")) return text;
  // Find the closing --- of the frontmatter block (starts searching after the opening ---)
  const closeIndex = text.indexOf("---", 3);
  if (closeIndex === -1) return text;
  return text.slice(closeIndex + 3).trim();
}

export const Route = createFileRoute("/skills")({ component: SkillsEditor });

const AGENT_META: Record<string, { label: string; short: string; color: string }> = {
  skills:    { label: "Knowledge Base", short: "KB", color: "text-primary bg-primary/10 border-primary/20" },
  shared:    { label: "Shared",         short: "SH", color: "text-info bg-info/10 border-info/20" },
  assess:    { label: "Assess",         short: "AS", color: "text-sky-600 bg-sky-500/10 border-sky-500/20" },
  convert:   { label: "Convert",        short: "CV", color: "text-violet-600 bg-violet-500/10 border-violet-500/20" },
  reconcile: { label: "Reconcile",      short: "RC", color: "text-amber-600 bg-amber-500/10 border-amber-500/20" },
  deploy:    { label: "Deploy",         short: "DP", color: "text-emerald-600 bg-emerald-500/10 border-emerald-500/20" },
};

const SKILL_DISPLAY_NAMES: Record<string, string> = {
  graph_context:          "discovery_graph_ingestion",
  risk_assessment:        "risk_tiering",
  hiveql_to_pyspark:      "spark_emr_iceberg",
  hiveql_repair:          "hive_to_athena_trino",
  dag_generation:         "controlm_to_mwaa",
  deployment_governance:  "sds_kms_security",
  semantic_comparison:    "reconciliation",
  artifact_validation:    "handover_package",
};

const totalCount = (index: Record<string, string[]>) =>
  Object.values(index).reduce((s, a) => s + a.length, 0);

function SkillsEditor() {
  const [index,    setIndex]    = useState<Record<string, string[]>>({});
  const [selected, setSelected] = useState<{ agent: string; filename: string } | null>(null);
  const [content,  setContent]  = useState("");
  const [original, setOriginal] = useState("");
  const [saving,   setSaving]   = useState(false);
  const [saved,    setSaved]    = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [mode, setMode] = useState<"edit" | "preview">("preview");

  const dirty     = content !== original;
  const lineCount = content.split("\n").length;
  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;

  useEffect(() => {
    fetch("/skills-api").then(r => r.json()).then(setIndex).catch(() => {});
  }, []);

  async function select(agent: string, filename: string) {
    const d = await fetch(`/skills-api/${agent}/${filename}`).then(r => r.json());
    setContent(d.content);
    setOriginal(d.content);
    setSelected({ agent, filename });
    setSaved(false);
    setMode("preview");
  }

  async function save() {
    if (!selected || !dirty) return;
    setSaving(true);
    await fetch(`/skills-api/${selected.agent}/${selected.filename}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    setOriginal(content);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <AppShell>
      <div className="h-full flex overflow-hidden bg-background">

        {/* ── Sidebar ─────────────────────────────────────────────────────── */}
        <aside className="w-60 shrink-0 border-r border-border bg-white flex flex-col overflow-hidden">

          {/* Sidebar header */}
          <div className="px-4 py-4 border-b border-border shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center">
                <BookOpen className="h-3.5 w-3.5 text-primary" />
              </div>
              <div>
                <div className="text-[13px] font-semibold text-foreground leading-none">Skills</div>
                <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
                  {totalCount(index)} files
                </div>
              </div>
            </div>
          </div>

          {/* File tree */}
          <div className="flex-1 overflow-y-auto py-2">
            {Object.entries(index).map(([agent, files]) => {
              const meta = AGENT_META[agent];
              return (
                <div key={agent} className="mb-1">
                  {/* Agent group header */}
                  <div className="flex items-center gap-2 px-3 py-1.5 mt-1">
                    {agent === "shared" ? (
                      <Globe className="h-3 w-3 text-muted-foreground/60" />
                    ) : (
                      <span className={`inline-flex items-center justify-center h-4 w-6 rounded text-[9px] font-mono font-bold border ${meta?.color ?? ""}`}>
                        {meta?.short ?? "??"}
                      </span>
                    )}
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-semibold">
                      {meta?.label ?? agent}
                    </span>
                    <span className="ml-auto text-[10px] text-muted-foreground/50 font-mono">{files.length}</span>
                  </div>

                  {/* Skill files */}
                  {files.map((f) => {
                    const isActive = selected?.agent === agent && selected?.filename === f;
                    const name = SKILL_DISPLAY_NAMES[f.replace(".md", "")] ?? f.replace(".md", "");
                    return (
                      <button key={f} onClick={() => select(agent, f)}
                        className={`w-full text-left flex items-center gap-2 pl-7 pr-3 py-1.5 text-[12px] font-mono transition-colors ${
                          isActive
                            ? "bg-primary/8 text-primary border-r-2 border-primary"
                            : "text-foreground/60 hover:text-foreground hover:bg-surface-2 border-r-2 border-transparent"
                        }`}>
                        <FileText className={`h-3 w-3 shrink-0 ${isActive ? "text-primary" : "text-muted-foreground/40"}`} />
                        <span className={isActive ? "font-medium" : ""}>{name}</span>
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </aside>

        {/* ── Editor pane ─────────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {!selected ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-muted-foreground">
              <div className="h-12 w-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center">
                <BookOpen className="h-5 w-5 opacity-40" />
              </div>
              <div className="text-center">
                <p className="text-[14px] font-medium text-foreground/60">No skill selected</p>
                <p className="text-[12px] mt-0.5">Pick a file from the sidebar</p>
              </div>
            </div>
          ) : (
            <>
              {/* Editor toolbar */}
              <div className="flex items-center gap-3 px-5 py-2.5 border-b border-border bg-white shrink-0">
                {/* Breadcrumb */}
                <div className="flex items-center gap-1.5 flex-1 min-w-0 font-mono text-[12px]">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${AGENT_META[selected.agent]?.color ?? ""}`}>
                    {AGENT_META[selected.agent]?.short ?? "??"}
                  </span>
                  <span className="text-muted-foreground/50">/</span>
                  <span className="text-foreground font-medium">{selected.filename}</span>
                  {dirty && (
                    <span className="ml-1 h-1.5 w-1.5 rounded-full bg-warning inline-block" title="Unsaved changes" />
                  )}
                </div>

                {/* Edit / Preview toggle */}
                <div className="flex items-center gap-0.5 border border-border rounded-md p-0.5 bg-surface-2/50">
                  {(["preview", "edit"] as const).map((m) => (
                    <button key={m} onClick={() => { setMode(m); if (m === "edit") setTimeout(() => textareaRef.current?.focus(), 50); }}
                      className={`inline-flex items-center gap-1.5 h-6 px-2.5 rounded text-[11px] font-medium transition ${
                        mode === m ? "bg-white shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
                      }`}>
                      {m === "preview" ? <Eye className="h-3 w-3" /> : <Pencil className="h-3 w-3" />}
                      {m === "preview" ? "Preview" : "Edit"}
                    </button>
                  ))}
                </div>

                {/* Cmd+S hint */}
                {mode === "edit" && dirty && !saving && (
                  <span className="text-[11px] font-mono text-muted-foreground/50 hidden sm:block">⌘S</span>
                )}

                {/* Save button */}
                <button onClick={save} disabled={!dirty || saving}
                  className={`inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-[12px] font-medium transition shrink-0 ${
                    saved  ? "bg-success/10 text-success border border-success/30" :
                    !dirty ? "text-muted-foreground/40 cursor-not-allowed" :
                    saving ? "bg-primary/10 text-primary border border-primary/20 cursor-not-allowed" :
                             "bg-primary text-white hover:bg-primary/90 shadow-sm"
                  }`}>
                  {saving ? <><Cpu className="h-3 w-3 animate-spin" /> Saving</> :
                   saved   ? <>✓ Saved</> :
                             <><Save className="h-3 w-3" /> Save</>}
                </button>
              </div>

              {/* Content area */}
              <div className="flex-1 overflow-hidden flex flex-col">
                {mode === "edit" ? (
                  <textarea
                    ref={textareaRef}
                    value={content}
                    onChange={e => { setContent(e.target.value); setSaved(false); }}
                    onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); save(); } }}
                    spellCheck={false}
                    className="flex-1 w-full resize-none font-mono text-[13px] leading-[1.7] text-foreground/90 bg-background p-6 focus:outline-none"
                    style={{ tabSize: 2 }}
                    placeholder="Skill content…"
                  />
                ) : (
                  <div className="flex-1 overflow-y-auto px-8 py-6">
                    <div
                      className="max-w-2xl prose prose-sm prose-neutral
                        [&_h1]:text-[20px] [&_h1]:font-semibold [&_h1]:mb-4 [&_h1]:mt-0
                        [&_h2]:text-[15px] [&_h2]:font-semibold [&_h2]:mb-3 [&_h2]:mt-6 [&_h2]:text-foreground
                        [&_h3]:text-[13px] [&_h3]:font-semibold [&_h3]:mb-2 [&_h3]:mt-5 [&_h3]:text-foreground/80
                        [&_p]:text-[13px] [&_p]:leading-relaxed [&_p]:mb-3 [&_p]:text-foreground/80
                        [&_ul]:text-[13px] [&_ul]:mb-3 [&_li]:mb-1 [&_li]:text-foreground/80
                        [&_strong]:text-foreground [&_strong]:font-semibold
                        [&_code]:text-[12px] [&_code]:font-mono [&_code]:bg-surface-2 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-foreground/90 [&_code]:border [&_code]:border-border
                        [&_pre]:bg-surface-2 [&_pre]:border [&_pre]:border-border [&_pre]:rounded-lg [&_pre]:p-4 [&_pre]:overflow-x-auto [&_pre]:mb-4
                        [&_pre_code]:bg-transparent [&_pre_code]:border-0 [&_pre_code]:p-0 [&_pre_code]:text-[12px]
                        [&_table]:border-collapse [&_table]:w-full [&_table]:mb-4 [&_table]:text-[12px]
                        [&_th]:border [&_th]:border-border [&_th]:bg-surface-2 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold [&_th]:text-[11px] [&_th]:uppercase [&_th]:tracking-wider [&_th]:text-muted-foreground
                        [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-2 [&_td]:text-foreground/80
                        [&_blockquote]:border-l-2 [&_blockquote]:border-primary/40 [&_blockquote]:pl-4 [&_blockquote]:text-muted-foreground [&_blockquote]:italic
                        [&_hr]:border-border [&_hr]:my-6"
                      dangerouslySetInnerHTML={{ __html: marked.parse(stripFrontmatter(content)) as string }}
                    />
                  </div>
                )}
              </div>

              {/* Status bar */}
              <div className="flex items-center gap-4 px-5 py-1.5 border-t border-border bg-surface-2/60 shrink-0">
                <span className="text-[11px] font-mono text-muted-foreground/60">
                  {lineCount} lines · {wordCount} words
                </span>
                <span className="text-[11px] font-mono text-muted-foreground/60">Markdown</span>
                {dirty && (
                  <span className="text-[11px] font-mono text-warning ml-auto">Unsaved changes</span>
                )}
                {saved && (
                  <span className="text-[11px] font-mono text-success ml-auto">Saved</span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
