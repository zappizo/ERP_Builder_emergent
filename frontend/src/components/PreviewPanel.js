import { useState, useEffect, useCallback } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import CodeViewer from "@/components/CodeViewer";
import { getPipelineStage } from "@/lib/api";
import { copyText, downloadFilesAsZip } from "@/lib/export";
import { toast } from "sonner";
import {
  LayoutDashboard, Database, Globe, Code2, ShieldCheck, FileJson, Package,
  Users, ShoppingCart, Briefcase, Settings, BarChart3, Layers, CheckCircle2,
  AlertTriangle, XCircle, Info, Download, Copy
} from "lucide-react";

const ICON_MAP = {
  package: Package, users: Users, "shopping-cart": ShoppingCart, briefcase: Briefcase,
  settings: Settings, "bar-chart": BarChart3, layers: Layers, database: Database,
  globe: Globe, code: Code2, "layout-dashboard": LayoutDashboard, default: Package,
};

function getIcon(name) {
  if (!name) return Package;
  const key = name.toLowerCase().replace(/_/g, "-");
  return ICON_MAP[key] || Package;
}

const TABS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "modules", label: "Modules", icon: Package },
  { id: "database", label: "Database", icon: Database },
  { id: "api", label: "API", icon: Globe },
  { id: "code", label: "Code", icon: Code2 },
  { id: "review", label: "Review", icon: ShieldCheck },
  { id: "json", label: "JSON", icon: FileJson },
];

export default function PreviewPanel({ project }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [stageData, setStageData] = useState({});
  const [loadingStage, setLoadingStage] = useState(null);
  const pipeline = project?.pipeline || {};
  const architecture = stageData.architecture?.output || pipeline.architecture?.output;
  const masterJson = stageData.json_transform?.output;
  const frontendCode = stageData.frontend_generation?.output;
  const backendCode = stageData.backend_generation?.output;
  const review = stageData.code_review?.output;

  const TAB_STAGE_MAP = {
    overview: "architecture", modules: "architecture", database: "architecture",
    api: "architecture", code: null, review: "code_review", json: "json_transform"
  };

  const loadStageData = useCallback(async (stage) => {
    if (!project?.id || stageData[stage] || pipeline[stage]?.status !== "complete") return;
    setLoadingStage(stage);
    try {
      const data = await getPipelineStage(project.id, stage);
      setStageData(prev => ({ ...prev, [stage]: data }));
    } catch { /* ignore */ }
    setLoadingStage(null);
  }, [project?.id, stageData, pipeline]);

  useEffect(() => {
    if (activeTab === "code") {
      if (pipeline.frontend_generation?.status === "complete" && !stageData.frontend_generation) loadStageData("frontend_generation");
      if (pipeline.backend_generation?.status === "complete" && !stageData.backend_generation) loadStageData("backend_generation");
    } else {
      const stage = TAB_STAGE_MAP[activeTab];
      if (stage) loadStageData(stage);
    }
  }, [activeTab, loadStageData, pipeline]);

  // Auto-load architecture when it completes
  useEffect(() => {
    if (pipeline.architecture?.status === "complete" && !stageData.architecture) {
      loadStageData("architecture");
    }
  }, [pipeline.architecture?.status, loadStageData]);

  return (
    <div className="h-full flex flex-col" data-testid="preview-panel">
      {/* Tabs */}
      <div className="flex items-center border-b border-[var(--zap-border)] bg-white px-4 shrink-0">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            data-testid={`preview-tab-${id}`}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-sm transition-all
              ${activeTab === id ? "tab-active" : "tab-inactive"}`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-6">
          {activeTab === "overview" && <OverviewTab architecture={architecture} pipeline={pipeline} project={project} />}
          {activeTab === "modules" && <ModulesTab architecture={architecture} />}
          {activeTab === "database" && <DatabaseTab architecture={architecture} />}
          {activeTab === "api" && <ApiTab architecture={architecture} />}
          {activeTab === "code" && <CodeTab projectName={project?.name} frontendCode={frontendCode} backendCode={backendCode} />}
          {activeTab === "review" && <ReviewTab review={review} />}
          {activeTab === "json" && <JsonTab masterJson={masterJson} />}
        </div>
      </ScrollArea>
    </div>
  );
}

function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in-up" data-testid="preview-empty-state">
      <div className="w-12 h-12 rounded-sm bg-[var(--zap-secondary)] flex items-center justify-center mb-4">
        <Icon className="w-6 h-6 text-[var(--zap-text-muted)]" />
      </div>
      <h3 className="text-lg font-semibold tracking-tight mb-1" style={{ fontFamily: 'var(--font-heading)' }}>{title}</h3>
      <p className="text-sm text-[var(--zap-text-muted)] max-w-sm">{description}</p>
    </div>
  );
}

/* --- OVERVIEW --- */
function OverviewTab({ architecture, pipeline, project }) {
  if (!architecture) {
    return <EmptyState icon={LayoutDashboard} title="No Architecture Yet" description="Complete the requirements gathering to see the overview." />;
  }
  const modules = architecture.modules || [];
  const techStack = architecture.tech_stack || {};
  const roles = architecture.user_roles || [];

  return (
    <div className="space-y-6 animate-fade-in-up" data-testid="overview-content">
      <div>
        <h2 className="text-2xl sm:text-3xl tracking-tight font-bold mb-1" style={{ fontFamily: 'var(--font-heading)' }}>
          {architecture.system_name || project?.name}
        </h2>
        <p className="text-sm text-[var(--zap-text-body)]">{architecture.description || ""}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Modules", value: modules.length },
          { label: "Entities", value: modules.reduce((sum, m) => sum + (m.entities?.length || 0), 0) },
          { label: "Endpoints", value: modules.reduce((sum, m) => sum + (m.api_endpoints?.length || 0), 0) },
          { label: "Roles", value: roles.length },
        ].map(({ label, value }) => (
          <div key={label} className="border border-[var(--zap-border)] p-4 bg-white rounded-sm">
            <p className="text-xs uppercase tracking-[0.15em] font-medium text-[var(--zap-text-muted)] mb-1">{label}</p>
            <p className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>{value}</p>
          </div>
        ))}
      </div>

      {/* Tech Stack */}
      <div>
        <h3 className="text-lg font-semibold tracking-tight mb-3" style={{ fontFamily: 'var(--font-heading)' }}>Tech Stack</h3>
        <div className="flex flex-wrap gap-2">
          {Object.entries(techStack).map(([key, val]) => (
            <div key={key} className="px-3 py-1.5 border border-[var(--zap-border)] bg-white rounded-sm text-sm">
              <span className="text-[var(--zap-text-muted)] mr-1">{key}:</span>
              <span className="font-medium text-[var(--zap-text-heading)]">{val}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Module List */}
      <div>
        <h3 className="text-lg font-semibold tracking-tight mb-3" style={{ fontFamily: 'var(--font-heading)' }}>Modules</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {modules.map((mod, i) => {
            const IconComp = getIcon(mod.icon);
            return (
              <div key={i} className={`module-card p-4 bg-white stagger-${i + 1} animate-fade-in-up`}>
                <div className="flex items-center gap-2 mb-2">
                  <IconComp className="w-4 h-4 text-[var(--zap-accent)]" />
                  <span className="font-semibold text-sm tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>{mod.name}</span>
                </div>
                <p className="text-xs text-[var(--zap-text-muted)] mb-2 line-clamp-2">{mod.description || ""}</p>
                <div className="flex flex-wrap gap-1">
                  {(mod.features || []).slice(0, 3).map((f, j) => (
                    <Badge key={j} variant="secondary" className="text-[10px] rounded-sm px-1.5 py-0">{f}</Badge>
                  ))}
                  {(mod.features?.length || 0) > 3 && (
                    <Badge variant="secondary" className="text-[10px] rounded-sm px-1.5 py-0">+{mod.features.length - 3}</Badge>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* --- MODULES --- */
function ModulesTab({ architecture }) {
  const [selected, setSelected] = useState(0);
  if (!architecture?.modules?.length) {
    return <EmptyState icon={Package} title="No Modules Yet" description="Architecture generation will produce module details." />;
  }
  const modules = architecture.modules;
  const mod = modules[selected];

  return (
    <div className="animate-fade-in-up" data-testid="modules-content">
      {/* Module Selector */}
      <div className="flex flex-wrap gap-2 mb-6">
        {modules.map((m, i) => (
          <button
            key={i}
            data-testid={`module-select-${i}`}
            onClick={() => setSelected(i)}
            className={`px-3 py-1.5 text-sm border rounded-sm transition-all ${
              i === selected
                ? "border-[var(--zap-accent)] bg-[var(--zap-accent)]/5 text-[var(--zap-accent)] font-medium"
                : "border-[var(--zap-border)] text-[var(--zap-text-muted)] hover:border-black/20"
            }`}
          >
            {m.name}
          </button>
        ))}
      </div>

      {/* Module Detail */}
      <div className="space-y-5">
        <div>
          <h2 className="text-xl font-bold tracking-tight mb-1" style={{ fontFamily: 'var(--font-heading)' }}>{mod.name}</h2>
          <p className="text-sm text-[var(--zap-text-body)]">{mod.description || ""}</p>
        </div>

        {/* Features */}
        {mod.features?.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold mb-2 uppercase tracking-[0.1em] text-[var(--zap-text-muted)]">Features</h4>
            <div className="grid grid-cols-2 gap-2">
              {mod.features.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-[var(--zap-text-body)]">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--zap-success)] shrink-0" />
                  {f}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Entities */}
        {mod.entities?.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold mb-2 uppercase tracking-[0.1em] text-[var(--zap-text-muted)]">Entities</h4>
            <div className="space-y-3">
              {mod.entities.map((entity, i) => (
                <div key={i} className="border border-[var(--zap-border)] bg-white rounded-sm overflow-hidden">
                  <div className="px-3 py-2 bg-[var(--zap-bg)] border-b border-[var(--zap-border)]">
                    <span className="text-sm font-semibold" style={{ fontFamily: 'var(--font-mono)' }}>{entity.name}</span>
                  </div>
                  <div className="divide-y divide-[var(--zap-border)]">
                    {(entity.fields || []).map((field, j) => (
                      <div key={j} className="px-3 py-1.5 flex items-center justify-between text-xs">
                        <span style={{ fontFamily: 'var(--font-mono)' }} className="text-[var(--zap-text-heading)]">{field.name}</span>
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="text-[10px] rounded-sm px-1.5 py-0 font-mono">{field.type}</Badge>
                          {field.required && <span className="text-[var(--zap-danger)] text-[10px]">required</span>}
                          {field.primary && <span className="text-[var(--zap-accent)] text-[10px]">PK</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Workflows */}
        {mod.workflows?.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold mb-2 uppercase tracking-[0.1em] text-[var(--zap-text-muted)]">Workflows</h4>
            {mod.workflows.map((wf, i) => (
              <div key={i} className="border border-[var(--zap-border)] bg-white p-3 rounded-sm mb-2">
                <p className="text-sm font-semibold mb-1">{wf.name}</p>
                <div className="flex items-center gap-1 flex-wrap">
                  {(wf.steps || []).map((step, j) => (
                    <span key={j} className="flex items-center gap-1">
                      <span className="text-xs px-2 py-0.5 bg-[var(--zap-bg)] border border-[var(--zap-border)] rounded-sm">{step}</span>
                      {j < wf.steps.length - 1 && <span className="text-[var(--zap-text-muted)]">&rarr;</span>}
                    </span>
                  ))}
                </div>
                {wf.trigger && <p className="text-xs text-[var(--zap-text-muted)] mt-1">Trigger: {wf.trigger}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* --- DATABASE --- */
function DatabaseTab({ architecture }) {
  const schema = architecture?.database_schema;
  if (!schema?.tables?.length) {
    return <EmptyState icon={Database} title="No Schema Yet" description="Database schema will be generated with the architecture." />;
  }
  return (
    <div className="space-y-4 animate-fade-in-up" data-testid="database-content">
      <h2 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>Database Schema</h2>
      <div className="space-y-3">
        {schema.tables.map((table, i) => (
          <div key={i} className="border border-[var(--zap-border)] bg-white rounded-sm overflow-hidden">
            <div className="px-3 py-2 bg-[var(--zap-bg)] border-b border-[var(--zap-border)] flex items-center justify-between">
              <span className="text-sm font-semibold" style={{ fontFamily: 'var(--font-mono)' }}>{table.name}</span>
              {table.module && <Badge variant="secondary" className="text-[10px] rounded-sm">{table.module}</Badge>}
            </div>
            <div className="divide-y divide-[var(--zap-border)]">
              {(table.fields || []).map((field, j) => (
                <div key={j} className="px-3 py-1.5 flex items-center justify-between text-xs">
                  <span style={{ fontFamily: 'var(--font-mono)' }} className="text-[var(--zap-text-heading)]">{field.name}</span>
                  <div className="flex items-center gap-2">
                    <span style={{ fontFamily: 'var(--font-mono)' }} className="text-[var(--zap-accent)]">{field.type}</span>
                    {field.constraints && <span className="text-[var(--zap-text-muted)]">{field.constraints}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {schema.relationships?.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold tracking-tight mb-3" style={{ fontFamily: 'var(--font-heading)' }}>Relationships</h3>
          <div className="space-y-1">
            {schema.relationships.map((rel, i) => (
              <div key={i} className="flex items-center gap-2 text-sm py-1">
                <span className="font-mono text-[var(--zap-accent)]">{rel.from_table}</span>
                <span className="text-[var(--zap-text-muted)]">&mdash;{rel.type}&mdash;&gt;</span>
                <span className="font-mono text-[var(--zap-accent)]">{rel.to_table}</span>
                {rel.foreign_key && <span className="text-xs text-[var(--zap-text-muted)]">(FK: {rel.foreign_key})</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* --- API --- */
function ApiTab({ architecture }) {
  const modules = architecture?.modules;
  if (!modules?.length) {
    return <EmptyState icon={Globe} title="No API Endpoints Yet" description="API structure will be generated with the architecture." />;
  }
  const METHOD_COLORS = { GET: "bg-emerald-100 text-emerald-700", POST: "bg-blue-100 text-blue-700", PUT: "bg-amber-100 text-amber-700", DELETE: "bg-red-100 text-red-700", PATCH: "bg-purple-100 text-purple-700" };

  return (
    <div className="space-y-5 animate-fade-in-up" data-testid="api-content">
      <h2 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>API Endpoints</h2>
      {modules.map((mod, i) => (
        mod.api_endpoints?.length > 0 && (
          <div key={i}>
            <h3 className="text-sm font-semibold uppercase tracking-[0.1em] text-[var(--zap-text-muted)] mb-2">{mod.name}</h3>
            <div className="space-y-1">
              {mod.api_endpoints.map((ep, j) => (
                <div key={j} className="flex items-center gap-3 py-1.5 px-3 border border-[var(--zap-border)] bg-white rounded-sm">
                  <Badge className={`${METHOD_COLORS[ep.method] || METHOD_COLORS.GET} text-[10px] uppercase tracking-widest rounded-sm border-0 font-mono w-14 justify-center`}>
                    {ep.method}
                  </Badge>
                  <span className="text-sm font-mono text-[var(--zap-text-heading)]">{ep.path}</span>
                  <span className="text-xs text-[var(--zap-text-muted)] ml-auto">{ep.description}</span>
                </div>
              ))}
            </div>
          </div>
        )
      ))}
    </div>
  );
}

/* --- CODE --- */
function CodeTab({ projectName, frontendCode, backendCode }) {
  const [codeType, setCodeType] = useState("frontend");
  const [downloadedBundle, setDownloadedBundle] = useState(false);
  const code = codeType === "frontend" ? frontendCode : backendCode;
  const frontendFiles = frontendCode?.files || [];
  const backendFiles = backendCode?.files || [];
  const combinedFiles = [
    ...frontendFiles.map(file => ({ ...file, path: `frontend/${file.path}` })),
    ...backendFiles.map(file => ({ ...file, path: `backend/${file.path}` })),
  ];
  const hasCombinedBundle = frontendFiles.length > 0 && backendFiles.length > 0;

  function archiveBaseName() {
    return String(projectName || "ai-erp-builder")
      .trim()
      .replace(/[<>:"/\\|?*\x00-\x1f]+/g, "-")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .toLowerCase();
  }

  function markDownloaded() {
    setDownloadedBundle(true);
    window.setTimeout(() => setDownloadedBundle(false), 2000);
  }

  function handleDownload() {
    if (!hasCombinedBundle) {
      toast.error("Both frontend and backend files need to be ready before downloading the full ZIP.");
      return;
    }

    try {
      const baseName = archiveBaseName() || "ai-erp-builder";
      downloadFilesAsZip(combinedFiles, {
        archiveName: `${baseName}-full-codebase`,
        rootFolder: baseName,
      });
      markDownloaded();
      toast.success("Frontend and backend code downloaded in one ZIP.");
    } catch (error) {
      toast.error("Couldn't download the full code ZIP right now.");
    }
  }

  if (!code?.files?.length) {
    return <EmptyState icon={Code2} title="No Code Generated Yet" description="Code will be generated after the architecture phase completes." />;
  }
  return (
    <div className="animate-fade-in-up" data-testid="code-content">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-2">
          {["frontend", "backend"].map(t => (
            <button
              key={t}
              data-testid={`code-type-${t}`}
              onClick={() => setCodeType(t)}
              className={`px-3 py-1.5 text-sm border rounded-sm transition-all capitalize ${
                t === codeType
                  ? "border-[var(--zap-accent)] bg-[var(--zap-accent)]/5 text-[var(--zap-accent)] font-medium"
                  : "border-[var(--zap-border)] text-[var(--zap-text-muted)] hover:border-black/20"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            data-testid="download-code-zip-btn"
            onClick={handleDownload}
            disabled={!hasCombinedBundle}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-sm transition-all ${
              hasCombinedBundle
                ? "border-[var(--zap-border)] text-[var(--zap-text-heading)] hover:border-[var(--zap-accent)] hover:text-[var(--zap-accent)]"
                : "border-[var(--zap-border)] text-[var(--zap-text-muted)] opacity-50 cursor-not-allowed"
            }`}
          >
            {downloadedBundle ? <CheckCircle2 className="w-3.5 h-3.5 text-[var(--zap-success)]" /> : <Download className="w-3.5 h-3.5" />}
            {downloadedBundle ? "Full code downloaded" : "Download full code ZIP"}
          </button>
        </div>
      </div>
      <CodeViewer files={code.files} />
    </div>
  );
}

/* --- REVIEW --- */
function ReviewTab({ review }) {
  if (!review) {
    return <EmptyState icon={ShieldCheck} title="No Review Yet" description="Code review will run after code generation completes." />;
  }
  const SEVERITY_ICON = { error: XCircle, warning: AlertTriangle, info: Info };
  const SEVERITY_COLOR = { error: "text-[var(--zap-danger)]", warning: "text-[var(--zap-warning)]", info: "text-[var(--zap-accent)]" };

  return (
    <div className="space-y-5 animate-fade-in-up" data-testid="review-content">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>Code Review</h2>
        <div className="flex items-center gap-2 px-3 py-1 border border-[var(--zap-border)] bg-white rounded-sm">
          <span className="text-sm text-[var(--zap-text-muted)]">Score:</span>
          <span className="text-lg font-bold" style={{ fontFamily: 'var(--font-heading)' }}>
            {review.overall_score || "N/A"}<span className="text-sm text-[var(--zap-text-muted)]">/10</span>
          </span>
        </div>
      </div>

      {review.summary && <p className="text-sm text-[var(--zap-text-body)]">{review.summary}</p>}

      {/* Issues */}
      {[review.frontend_review, review.backend_review].map((rev, i) => (
        rev?.issues?.length > 0 && (
          <div key={i}>
            <h3 className="text-sm font-semibold uppercase tracking-[0.1em] text-[var(--zap-text-muted)] mb-2">
              {i === 0 ? "Frontend" : "Backend"} Issues
            </h3>
            <div className="space-y-2">
              {rev.issues.map((issue, j) => {
                const SevIcon = SEVERITY_ICON[issue.severity] || Info;
                return (
                  <div key={j} className="flex gap-2 p-3 border border-[var(--zap-border)] bg-white rounded-sm">
                    <SevIcon className={`w-4 h-4 shrink-0 mt-0.5 ${SEVERITY_COLOR[issue.severity] || ""}`} />
                    <div>
                      <p className="text-sm text-[var(--zap-text-heading)]">{issue.description}</p>
                      {issue.suggestion && <p className="text-xs text-[var(--zap-text-muted)] mt-1">{issue.suggestion}</p>}
                      {issue.file && <p className="text-xs font-mono text-[var(--zap-accent)] mt-1">{issue.file}</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )
      ))}

      {/* Security */}
      {review.security_checks && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.1em] text-[var(--zap-text-muted)] mb-2">Security Checks</h3>
          <div className="space-y-1">
            {(review.security_checks.passed || []).map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="w-3.5 h-3.5 text-[var(--zap-success)]" /><span>{c}</span>
              </div>
            ))}
            {(review.security_checks.warnings || []).map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <AlertTriangle className="w-3.5 h-3.5 text-[var(--zap-warning)]" /><span>{c}</span>
              </div>
            ))}
            {(review.security_checks.critical || []).map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <XCircle className="w-3.5 h-3.5 text-[var(--zap-danger)]" /><span>{c}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {review.recommendations?.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.1em] text-[var(--zap-text-muted)] mb-2">Recommendations</h3>
          <ul className="space-y-1">
            {review.recommendations.map((r, i) => (
              <li key={i} className="text-sm text-[var(--zap-text-body)] pl-3 border-l-2 border-[var(--zap-accent)]">{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* --- JSON --- */
function JsonTab({ masterJson }) {
  const [copied, setCopied] = useState(false);

  async function handleCopyJson() {
    const success = await copyText(JSON.stringify(masterJson, null, 2));
    if (!success) {
      toast.error("Couldn't copy the JSON right now.");
      return;
    }

    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
    toast.success("JSON copied to clipboard.");
  }

  if (!masterJson) {
    return <EmptyState icon={FileJson} title="No Master JSON Yet" description="The JSON schema will be generated after architecture design." />;
  }
  return (
    <div className="animate-fade-in-up" data-testid="json-content">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h2 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>Master JSON Schema</h2>
        <button
          data-testid="copy-json-btn"
          onClick={handleCopyJson}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--zap-border)] rounded-sm text-[var(--zap-text-heading)] hover:border-[var(--zap-accent)] hover:text-[var(--zap-accent)] transition-all"
        >
          {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-[var(--zap-success)]" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied JSON" : "Copy JSON"}
        </button>
      </div>
      <div className="code-block max-h-[calc(100vh-200px)] overflow-auto">
        <pre className="text-xs leading-relaxed">{JSON.stringify(masterJson, null, 2)}</pre>
      </div>
    </div>
  );
}
