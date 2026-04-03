import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject, getMessages, sendChat } from "@/lib/api";
import ChatPanel from "@/components/ChatPanel";
import PreviewPanel from "@/components/PreviewPanel";
import PipelineProgress from "@/components/PipelineProgress";
import { Zap, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

const POLLING_STATUSES = ["INIT", "ANALYZING", "GATHERING", "ARCHITECTING", "TRANSFORMING", "GENERATING_FRONTEND", "GENERATING_BACKEND", "REVIEWING"];

export default function ProjectBuilder() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const initialSent = useRef(false);
  const pollRef = useRef(null);
  const projectStatus = project?.status;

  const fetchProject = useCallback(async () => {
    try {
      const data = await getProject(id);
      setProject(data);
      return data;
    } catch {
      toast.error("Failed to load project");
      return null;
    }
  }, [id]);

  const fetchMessages = useCallback(async () => {
    try {
      const data = await getMessages(id);
      setMessages(data);
    } catch { /* ignore */ }
  }, [id]);

  // Initial load
  useEffect(() => {
    setLoading(true);
    Promise.all([fetchProject(), fetchMessages()]).finally(() => setLoading(false));
  }, [fetchProject, fetchMessages]);

  const handleSend = useCallback(async (content) => {
    if (!content.trim() || chatLoading) return;
    setMessages(prev => [...prev, { id: Date.now().toString(), role: "user", content, created_at: new Date().toISOString() }]);
    setChatLoading(true);
    try {
      await sendChat(id, content);
      await fetchMessages();
      await fetchProject();
    } catch {
      toast.error("Failed to send message");
    } finally {
      setChatLoading(false);
    }
  }, [chatLoading, id, fetchMessages, fetchProject]);

  // Auto-send initial prompt
  useEffect(() => {
    if (!project?.prompt || project?.status !== "INIT" || initialSent.current) {
      return;
    }
    if (messages.length > 0) {
      return;
    }
    const projectAgeMs = Date.now() - new Date(project.created_at).getTime();
    if (projectAgeMs < 2000) {
      return;
    }
    if (chatLoading) {
      return;
    }
    if (messages.length === 0) {
      initialSent.current = true;
      handleSend(project.prompt);
    }
  }, [project, messages.length, chatLoading, handleSend]);

  // Polling during auto-pipeline
  useEffect(() => {
    if (projectStatus && POLLING_STATUSES.includes(projectStatus)) {
      pollRef.current = setInterval(async () => {
        const p = await fetchProject();
        await fetchMessages();
        if (p && !POLLING_STATUSES.includes(p.status)) {
          clearInterval(pollRef.current);
        }
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectStatus, fetchProject, fetchMessages]);

  if (loading || !project) {
    return (
      <div className="h-screen flex items-center justify-center" data-testid="builder-loading">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-[var(--zap-accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--zap-text-muted)]">Loading project...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col" data-testid="project-builder-page">
      {/* Header */}
      <header className="h-12 bg-white/70 backdrop-blur-xl border-b border-black/5 flex items-center px-4 gap-3 shrink-0 z-50">
        <button
          data-testid="back-to-dashboard-btn"
          onClick={() => navigate("/")}
          className="p-1 hover:bg-black/5 rounded-sm transition-colors"
        >
          <ArrowLeft className="w-4 h-4 text-[var(--zap-text-body)]" />
        </button>
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 bg-[var(--zap-accent)] rounded-sm flex items-center justify-center">
            <Zap className="w-3 h-3 text-white" />
          </div>
          <span className="text-sm font-bold tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>
            {project.name}
          </span>
        </div>
        <div className="flex-1 mx-4">
          <PipelineProgress pipeline={project.pipeline} status={project.status} />
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat Panel - Left 35% */}
        <div className="w-[35%] min-w-[320px] border-r border-[var(--zap-border)] flex flex-col bg-white">
          <ChatPanel
            messages={messages}
            onSend={handleSend}
            isLoading={chatLoading}
            projectStatus={project.status}
            analysisStage={project.pipeline?.requirement_analysis?.output}
            requirementStage={project.pipeline?.requirement_gathering?.output}
            requirementCompleteness={project.requirement_completeness}
          />
        </div>

        {/* Preview Panel - Right 65% */}
        <div className="flex-1 overflow-hidden bg-[var(--zap-bg)]">
          <PreviewPanel project={project} />
        </div>
      </div>
    </div>
  );
}
