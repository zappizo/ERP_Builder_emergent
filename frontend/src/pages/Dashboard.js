import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { listProjects, listProjectTemplates, createProject, deleteProject } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Plus, Zap, Trash2, ArrowRight, LayoutDashboard, Database, Code2, GitBranch } from "lucide-react";

const STATUS_COLORS = {
  INIT: "bg-gray-200 text-gray-700",
  ANALYZING: "bg-blue-100 text-blue-700",
  GATHERING: "bg-amber-100 text-amber-700",
  ARCHITECTING: "bg-indigo-100 text-indigo-700",
  TRANSFORMING: "bg-purple-100 text-purple-700",
  GENERATING_FRONTEND: "bg-cyan-100 text-cyan-700",
  GENERATING_BACKEND: "bg-teal-100 text-teal-700",
  REVIEWING: "bg-orange-100 text-orange-700",
  COMPLETE: "bg-emerald-100 text-emerald-700",
  ERROR: "bg-red-100 text-red-700",
};

const EXAMPLES = [
  "I want an ERP for a manufacturing company with inventory, production planning, and sales management",
  "Build me a retail ERP with POS, inventory tracking, CRM, and supplier management",
  "Create an ERP for a healthcare clinic with patient management, appointments, billing, and pharmacy",
  "Design an ERP for a construction company with project management, procurement, and HR",
];

const FALLBACK_TEMPLATES = [
  {
    id: "template_1",
    name: "Template 1",
    display_name: "Template 1 - Athena",
    reference_project: "Athena",
    summary: "Dark control-center ERP shell with glass panels, staged workflows, and action-heavy operations views.",
    source_files: [
      { relative_path: "Template/Template 1/style.css", role: "theme" },
      { relative_path: "Template/Template 1/templates.ts", role: "ui-shell" },
      { relative_path: "Template/Template 1/main.ts", role: "app-entry" },
    ],
  },
  {
    id: "template_2",
    name: "Template 2",
    display_name: "Template 2 - Print Co",
    reference_project: "Print Co",
    summary: "Warm paper-toned ERP shell with horizontal module navigation, structured tables, and export-first actions.",
    source_files: [
      { relative_path: "Template/Template 2/styles.css", role: "theme" },
      { relative_path: "Template/Template 2/app.js", role: "ui-shell" },
      { relative_path: "Template/Template 2/ui-enhance.js", role: "ui-enhancements" },
    ],
  },
];

const CREATE_RECOVERY_DELAY_MS = 2500;
const CREATE_RECOVERY_POLL_MS = 1500;
const CREATE_RECOVERY_ATTEMPTS = 8;
const RECENT_PROJECT_WINDOW_MS = 3 * 60 * 1000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRecentProjectMatch(project, name, prompt, templateId) {
  if (!project) return false;
  if ((project.name || "").trim() !== name) return false;
  if ((project.prompt || "").trim() !== prompt) return false;
  if ((project.selected_template_id || "").trim() !== (templateId || "").trim()) return false;

  const timestamp = Date.parse(project.created_at || project.updated_at || "");
  if (!Number.isFinite(timestamp)) return false;

  return Date.now() - timestamp <= RECENT_PROJECT_WINDOW_MS;
}

function describeCreateError(error) {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => item?.msg || item?.message || "Validation error")
      .filter(Boolean)
      .join("; ");
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  return "Project creation failed. Please check the backend connection and try again.";
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [templates, setTemplates] = useState(FALLBACK_TEMPLATES);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [templateId, setTemplateId] = useState(FALLBACK_TEMPLATES[0].id);
  const [creating, setCreating] = useState(false);
  const [createStatusMessage, setCreateStatusMessage] = useState("");

  useEffect(() => {
    loadProjects();
    loadTemplates();
  }, []);

  async function loadProjects() {
    try {
      const data = await listProjects();
      setProjects(data);
    } catch { /* ignore */ }
  }

  async function loadTemplates() {
    try {
      const data = await listProjectTemplates();
      if (Array.isArray(data) && data.length > 0) {
        setTemplates(data);
        setTemplateId((current) => current || data[0].id);
      }
    } catch { /* ignore */ }
  }

  async function findRecentCreatedProject(projectName, projectPrompt, selectedTemplateId) {
    try {
      const items = await listProjects();
      return items
        .filter((project) => isRecentProjectMatch(project, projectName, projectPrompt, selectedTemplateId))
        .sort((a, b) => Date.parse(b.created_at || b.updated_at || "") - Date.parse(a.created_at || a.updated_at || ""))[0] || null;
    } catch {
      return null;
    }
  }

  async function handleCreate() {
    if (!name.trim() || !prompt.trim()) { toast.error("Fill in all fields"); return; }
    const projectName = name.trim();
    const projectPrompt = prompt.trim();
    const selectedTemplateId = templateId || templates[0]?.id || FALLBACK_TEMPLATES[0].id;
    const selectedTemplate = templates.find((item) => item.id === selectedTemplateId) || FALLBACK_TEMPLATES[0];
    setCreating(true);
    setCreateStatusMessage(`Creating the project shell with ${selectedTemplate.display_name}. The builder page should open in a moment.`);

    let navigated = false;
    const openProject = (project, source) => {
      navigated = true;
      setOpen(false);
      navigate(`/project/${project.id}`, {
        state: {
          createSource: source,
          justCreated: true,
        },
      });
    };

    const recoveryPromise = (async () => {
      await sleep(CREATE_RECOVERY_DELAY_MS);
      if (navigated) return null;

      setCreateStatusMessage(
        "The project may already be created. Checking the latest projects and opening it automatically..."
      );

      for (let attempt = 0; attempt < CREATE_RECOVERY_ATTEMPTS && !navigated; attempt += 1) {
        const existingProject = await findRecentCreatedProject(projectName, projectPrompt, selectedTemplateId);
        if (existingProject) {
          return existingProject;
        }
        await sleep(CREATE_RECOVERY_POLL_MS);
      }

      return null;
    })();

    try {
      const createRequest = createProject(projectName, projectPrompt, selectedTemplateId);
      const firstResult = await Promise.race([
        createRequest.then((project) => ({ source: "create-response", project })),
        recoveryPromise.then((project) => (project ? { source: "recovered-project", project } : null)),
      ]);

      if (firstResult?.project && !navigated) {
        openProject(firstResult.project, firstResult.source);
        return;
      }

      const project = await createRequest;
      if (!navigated) {
        openProject(project, "create-response");
      }
    } catch (e) {
      const existingProject = await findRecentCreatedProject(projectName, projectPrompt, selectedTemplateId);
      if (existingProject && !navigated) {
        openProject(existingProject, "recovered-after-error");
        return;
      }

      const errorMessage = describeCreateError(e);
      setCreateStatusMessage(errorMessage);
      toast.error(errorMessage);
      setCreating(false);
      return;
    }

    setCreating(false);
  }

  async function handleDelete(e, id) {
    e.stopPropagation();
    try {
      await deleteProject(id);
      setProjects(prev => prev.filter(p => p.id !== id));
      toast.success("Project deleted");
    } catch { toast.error("Delete failed"); }
  }

  function selectExample(ex) {
    setPrompt(ex);
    setName(ex.split(" for ")[1]?.split(" with")[0] || "My ERP Project");
  }

  const activeTemplate = templates.find((item) => item.id === templateId) || templates[0] || FALLBACK_TEMPLATES[0];

  return (
    <div className="min-h-screen" data-testid="dashboard-page">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/70 backdrop-blur-xl border-b border-black/5">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-[var(--zap-accent)] rounded-sm flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>
              Zappizo
            </span>
          </div>
          <Button
            data-testid="new-project-btn"
            onClick={() => setOpen(true)}
            className="bg-[var(--zap-primary)] text-white hover:bg-black/80 rounded-sm h-8 px-4 text-sm"
          >
            <Plus className="w-4 h-4 mr-1" /> New Project
          </Button>
        </div>
      </header>

      {/* Hero */}
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-10">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.2em] font-medium text-[var(--zap-text-muted)] mb-4">
            AI-Powered ERP Builder
          </p>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-black leading-[1.05] mb-5"
              style={{ fontFamily: 'var(--font-heading)' }}>
            Transform ideas into<br />enterprise systems
          </h1>
          <p className="text-base text-[var(--zap-text-body)] leading-relaxed max-w-lg mb-8">
            Describe your business in plain language. Zappizo's AI agents will design the architecture,
            generate the database schema, API endpoints, and production-ready code.
          </p>
          <Button
            data-testid="hero-get-started-btn"
            onClick={() => setOpen(true)}
            className="bg-[var(--zap-accent)] text-white hover:opacity-90 rounded-sm h-10 px-6 text-sm font-medium"
          >
            Get Started <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>

        {/* Feature Chips */}
        <div className="flex flex-wrap gap-3 mt-12 mb-16">
          {[
            { icon: LayoutDashboard, label: "Architecture Design" },
            { icon: Database, label: "Schema Generation" },
            { icon: Code2, label: "Code Generation" },
            { icon: GitBranch, label: "Version Control" },
          ].map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-2 px-3 py-1.5 border border-[var(--zap-border)] rounded-sm text-sm text-[var(--zap-text-body)]">
              <Icon className="w-3.5 h-3.5 text-[var(--zap-text-muted)]" />
              {label}
            </div>
          ))}
        </div>

        {/* Projects Grid */}
        {projects.length > 0 && (
          <div>
            <h2 className="text-2xl sm:text-3xl tracking-tight font-bold mb-6"
                style={{ fontFamily: 'var(--font-heading)' }}>
              Your Projects
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <div
                  key={p.id}
                  data-testid={`project-card-${p.id}`}
                  onClick={() => navigate(`/project/${p.id}`)}
                  className="module-card p-5 bg-white cursor-pointer group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-[var(--zap-text-heading)] tracking-tight truncate pr-2"
                        style={{ fontFamily: 'var(--font-heading)' }}>
                      {p.name}
                    </h3>
                    <button
                      data-testid={`delete-project-${p.id}`}
                      onClick={(e) => handleDelete(e, p.id)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-red-50 rounded-sm"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-red-500" />
                    </button>
                  </div>
                  <p className="text-sm text-[var(--zap-text-muted)] line-clamp-2 mb-4">{p.prompt}</p>
                  {p.selected_template_name && (
                    <p className="text-xs text-[var(--zap-text-muted)] mb-4">
                      ERP template: {p.selected_template_name}
                    </p>
                  )}
                  <div className="flex items-center justify-between">
                    <Badge className={`${STATUS_COLORS[p.status] || STATUS_COLORS.INIT} text-xs uppercase tracking-widest rounded-sm border-0`}>
                      {p.status}
                    </Badge>
                    <span className="text-xs text-[var(--zap-text-muted)]">
                      {new Date(p.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Create Dialog */}
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen);
          if (!nextOpen) {
            setCreating(false);
          }
          setCreateStatusMessage("");
        }}
      >
        <DialogContent className="sm:max-w-lg rounded-sm border-[var(--zap-border)]" data-testid="create-project-dialog">
          <DialogHeader>
            <DialogTitle className="text-xl tracking-tight font-bold" style={{ fontFamily: 'var(--font-heading)' }}>
              Create New ERP Project
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium text-[var(--zap-text-heading)] mb-1.5 block">Project Name</label>
              <Input
                data-testid="project-name-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Manufacturing ERP"
                className="rounded-sm border-[var(--zap-border)] focus-visible:ring-[var(--zap-accent)]"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-[var(--zap-text-heading)] mb-1.5 block">
                Describe Your ERP
              </label>
              <Textarea
                data-testid="project-prompt-input"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe the ERP system you want to build..."
                rows={4}
                className="rounded-sm border-[var(--zap-border)] focus-visible:ring-[var(--zap-accent)] resize-none"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-[var(--zap-text-heading)] mb-1.5 block">
                ERP Template
              </label>
              <select
                data-testid="project-template-select"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className="flex h-10 w-full rounded-sm border border-[var(--zap-border)] bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--zap-accent)]"
              >
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.display_name}
                  </option>
                ))}
              </select>
              {activeTemplate && (
                <div className="mt-3 rounded-sm border border-[var(--zap-border)] bg-[var(--zap-bg)] px-3 py-2.5">
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-[var(--zap-text-muted)]">
                    Reference UI/UX
                  </p>
                  <p className="mt-1 text-sm text-[var(--zap-text-heading)]">
                    {activeTemplate.display_name} uses {activeTemplate.reference_project} as the generated ERP reference.
                  </p>
                  <p className="mt-2 text-xs text-[var(--zap-text-body)] leading-relaxed">
                    {activeTemplate.summary}
                  </p>
                  <p className="mt-2 text-[11px] text-[var(--zap-text-muted)]">
                    Source files: {(activeTemplate.source_files || []).map((file) => file.relative_path).join(", ")}
                  </p>
                </div>
              )}
            </div>
            <div>
              <p className="text-xs text-[var(--zap-text-muted)] mb-2">Quick examples:</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    data-testid={`example-prompt-${i}`}
                    onClick={() => selectExample(ex)}
                    className="text-xs text-left px-2.5 py-1.5 border border-[var(--zap-border)] rounded-sm text-[var(--zap-text-muted)] hover:border-[var(--zap-accent)] hover:text-[var(--zap-accent)] transition-colors"
                  >
                    {ex.length > 60 ? ex.slice(0, 60) + "..." : ex}
                  </button>
                ))}
              </div>
            </div>
            <div className="rounded-sm border border-[var(--zap-border)] bg-[var(--zap-bg)] px-3 py-2.5">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-[var(--zap-text-muted)]">
                What Happens Next
              </p>
              <p className="mt-1 text-xs text-[var(--zap-text-body)] leading-relaxed">
                This button only creates the project shell. Once that returns, the builder page opens and shows the live AI stages:
                analysis, clarification, architecture, ERP blueprint, frontend, backend, and review. The selected template only affects the ERP being generated, not this builder UI.
              </p>
            </div>
            {createStatusMessage && (
              <div
                data-testid="create-project-status"
                className={`rounded-sm px-3 py-2 text-xs leading-relaxed ${
                  creating
                    ? "border border-[var(--zap-accent)]/20 bg-[var(--zap-accent)]/5 text-[var(--zap-text-body)]"
                    : "border border-red-200 bg-red-50 text-red-700"
                }`}
              >
                {createStatusMessage}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              data-testid="cancel-create-btn"
              variant="outline"
              onClick={() => setOpen(false)}
              className="rounded-sm border-[var(--zap-border)]"
            >
              Cancel
            </Button>
            <Button
              data-testid="create-project-submit-btn"
              onClick={handleCreate}
              disabled={creating}
              className="bg-[var(--zap-accent)] text-white hover:opacity-90 rounded-sm"
            >
              {creating ? "Opening Builder..." : "Create Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
