import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Bot, User } from "lucide-react";

const STAGE_DETAILS = {
  INIT: {
    title: "Project shell created",
    summary: "The backend should start processing your prompt right away. If it stays here, the page will retry automatically.",
    model: "No LLM call yet",
    api: "POST /api/projects",
    action: "Wait a moment while the builder page syncs with the backend.",
  },
  ANALYZING: {
    title: "Requirement analysis",
    summary: "The app is reading your prompt and inferring the business type, scale, modules, and missing details.",
    model: "Configured analysis model",
    api: "OpenRouter /api/v1/chat/completions",
    action: "The UI is polling /api/projects/{id} and /api/projects/{id}/messages.",
  },
  GATHERING: {
    title: "Clarifying requirements",
    summary: "The planner is asking focused follow-up questions before it locks the final ERP requirements.",
    model: "Configured analysis model",
    api: "OpenRouter /api/v1/chat/completions via POST /api/projects/{id}/chat",
    action: "Reply in the chat box to move the project to architecture and generation.",
  },
  ARCHITECTING: {
    title: "Planning the ERP architecture",
    summary: "The app is updating the current ERP architecture in place, keeping unaffected parts intact.",
    model: "deepseek/deepseek-r1-distill-llama-70b",
    api: "OpenRouter /api/v1/chat/completions",
    action: "The builder is working in the background.",
  },
  TRANSFORMING: {
    title: "Generating blueprint specs",
    summary: "The current JSON and Markdown blueprint are being revised in place instead of restarting from scratch.",
    model: "deepseek/deepseek-r1-distill-llama-70b",
    api: "OpenRouter /api/v1/chat/completions",
    action: "The next step is parallel frontend and backend generation.",
  },
  GENERATING_FRONTEND: {
    title: "Generating code",
    summary: "Frontend and backend code are being updated over the current ERP version, not rebuilt from zero.",
    model: "deepseek/deepseek-chat-v3-0324",
    api: "OpenRouter /api/v1/chat/completions",
    action: "The backend also enters generation during this stage.",
  },
  GENERATING_BACKEND: {
    title: "Generating code",
    summary: "Frontend and backend code are being updated over the current ERP version, not rebuilt from zero.",
    model: "deepseek/deepseek-chat-v3-0324",
    api: "OpenRouter /api/v1/chat/completions",
    action: "The builder is packaging generated files and saving artifacts.",
  },
  REVIEWING: {
    title: "Reviewing generated code",
    summary: "The final model pass is checking the generated code for quality and structure before completion.",
    model: "deepseek/deepseek-chat-v3-0324",
    api: "OpenRouter /api/v1/chat/completions",
    action: "When this finishes, the project moves to COMPLETE.",
  },
  COMPLETE: {
    title: "ERP ready",
    summary: "The blueprint, generated code bundles, and review output are available in the preview tabs.",
    model: "No active LLM call",
    api: "Read-only UI polling",
    action: "You can inspect outputs or ask for revisions. New requests apply on top of the current generated version.",
  },
  ERROR: {
    title: "Generation failed",
    summary: "A backend stage failed before the project could finish.",
    model: "See backend job error",
    api: "Check the latest stage and retry",
    action: "Use the chat to refine the request or retry generation.",
  },
};

function clampPercent(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return Math.max(0, Math.min(100, Math.round(value * 100)));
}

function renderMarkdown(text) {
  if (!text) return "";
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');
}

function summarizeMessage(text) {
  const normalized = (text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return null;
  if (normalized.length <= 180) return normalized;
  return `${normalized.slice(0, 177)}...`;
}

export default function ChatPanel({
  messages,
  onSend,
  isLoading,
  projectStatus,
  analysisStage,
  requirementStage,
  requirementCompleteness,
}) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const stageInfo = STAGE_DETAILS[projectStatus] || STAGE_DETAILS.INIT;
  const latestAssistantMessage = [...messages].reverse().find((msg) => msg.role === "assistant")?.content;
  const requirementMeta = requirementStage && typeof requirementStage === "object" ? requirementStage : null;
  const analysisMeta = analysisStage && typeof analysisStage === "object" ? analysisStage : null;
  const liveModel = requirementMeta?.analysis_model || stageInfo.model;
  const liveSummary =
    (projectStatus === "GATHERING" ? requirementMeta?.progress_summary : null) ||
    (projectStatus === "ANALYZING" ? analysisMeta?.summary : null) ||
    (projectStatus === "GATHERING" ? analysisMeta?.summary : null) ||
    stageInfo.summary;
  const liveAction = requirementMeta?.question_rationale
    ? `Next question focus: ${requirementMeta.question_rationale}.`
    : stageInfo.action;
  const missingTopics = Array.isArray(requirementMeta?.missing_topics) ? requirementMeta.missing_topics.slice(0, 4) : [];
  const capturedTopics = Array.isArray(requirementMeta?.captured_topics) ? requirementMeta.captured_topics.slice(0, 4) : [];
  const discoveryPercent = clampPercent(
    typeof requirementMeta?.completeness_score === "number"
      ? requirementMeta.completeness_score
      : requirementCompleteness,
  );

  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (el) el.scrollTop = el.scrollHeight;
    }
  }, [messages, isLoading]);

  function handleSubmit(e) {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput("");
  }

  const canChat = ["INIT", "GATHERING", "COMPLETE", "ERROR"].includes(projectStatus);

  return (
    <div className="flex flex-col h-full" data-testid="chat-panel">
      {/* Chat Header */}
      <div className="px-4 py-3 border-b border-[var(--zap-border)]">
        <h3 className="text-sm font-semibold tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>
          AI Assistant
        </h3>
        <p className="text-xs text-[var(--zap-text-muted)] mt-0.5">
          {projectStatus === "GATHERING" ? "Gathering requirements..." :
           projectStatus === "COMPLETE" ? "Ready for modifications" :
           ["ARCHITECTING","TRANSFORMING","GENERATING_FRONTEND","GENERATING_BACKEND","REVIEWING"].includes(projectStatus) ?
           "Building your ERP..." : "Describe your ERP system"}
        </p>
      </div>

      <div className="px-4 py-3 border-b border-[var(--zap-border)] bg-[var(--zap-bg)]/60" data-testid="live-process-card">
        <div className="rounded-sm border border-[var(--zap-border)] bg-white p-3 space-y-2">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[var(--zap-text-muted)]">
              Live Process
            </p>
            <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--zap-text-muted)]">
              {projectStatus || "INIT"}
            </span>
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--zap-text-heading)]">{stageInfo.title}</p>
            <p className="mt-1 text-xs leading-relaxed text-[var(--zap-text-body)]">{liveSummary}</p>
          </div>
          <div className="space-y-1.5 text-xs text-[var(--zap-text-body)]">
            <p><span className="font-medium text-[var(--zap-text-heading)]">Model:</span> {liveModel}</p>
            <p><span className="font-medium text-[var(--zap-text-heading)]">API:</span> {stageInfo.api}</p>
            <p><span className="font-medium text-[var(--zap-text-heading)]">Next:</span> {liveAction}</p>
            {discoveryPercent !== null && ["ANALYZING", "GATHERING", "COMPLETE"].includes(projectStatus) && (
              <p><span className="font-medium text-[var(--zap-text-heading)]">Coverage:</span> {discoveryPercent}%</p>
            )}
            {latestAssistantMessage && (
              <p><span className="font-medium text-[var(--zap-text-heading)]">Latest update:</span> {summarizeMessage(latestAssistantMessage)}</p>
            )}
          </div>
          {capturedTopics.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {capturedTopics.map((topic) => (
                <span
                  key={`captured-${topic}`}
                  className="rounded-full bg-[var(--zap-accent)]/10 px-2 py-1 text-[10px] font-medium text-[var(--zap-accent)]"
                >
                  {topic}
                </span>
              ))}
            </div>
          )}
          {missingTopics.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {missingTopics.map((topic) => (
                <span
                  key={`missing-${topic}`}
                  className="rounded-full border border-[var(--zap-border)] px-2 py-1 text-[10px] font-medium text-[var(--zap-text-body)]"
                >
                  Need: {topic}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <ScrollArea ref={scrollRef} className="flex-1 px-4 py-3">
        <div className="space-y-3">
          {messages.length === 0 && !isLoading && (
            <div className="text-center py-12 animate-fade-in-up" data-testid="chat-empty-state">
              <Bot className="w-8 h-8 text-[var(--zap-text-muted)] mx-auto mb-3" />
              <p className="text-sm text-[var(--zap-text-muted)]">
                Your AI assistant is ready.<br />
                Describe the ERP system you want to build.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={msg.id || i}
              className={`flex gap-2 animate-fade-in-up ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              data-testid={`chat-message-${msg.role}-${i}`}
            >
              {msg.role !== "user" && (
                <div className="w-6 h-6 rounded-sm bg-[var(--zap-accent)]/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5 text-[var(--zap-accent)]" />
                </div>
              )}
              <div className={`max-w-[85%] px-3 py-2 text-sm leading-relaxed ${
                msg.role === "user" ? "chat-msg-user" : "chat-msg-assistant"
              }`}>
                <div
                  className="chat-content"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                />
              </div>
              {msg.role === "user" && (
                <div className="w-6 h-6 rounded-sm bg-[var(--zap-primary)] flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-3.5 h-3.5 text-white" />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-2 animate-fade-in-up" data-testid="chat-loading-indicator">
              <div className="w-6 h-6 rounded-sm bg-[var(--zap-accent)]/10 flex items-center justify-center shrink-0">
                <Bot className="w-3.5 h-3.5 text-[var(--zap-accent)]" />
              </div>
              <div className="chat-msg-assistant px-3 py-3">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-[var(--zap-border)]">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            data-testid="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={canChat ? "Type your message..." : "Processing..."}
            disabled={!canChat || isLoading}
            className="flex-1 h-9 px-3 text-sm border border-[var(--zap-border)] rounded-sm bg-white
                       focus:outline-none focus:ring-2 focus:ring-[var(--zap-accent)] focus:ring-offset-1
                       disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ fontFamily: 'var(--font-body)' }}
          />
          <Button
            data-testid="chat-send-btn"
            type="submit"
            disabled={!canChat || isLoading || !input.trim()}
            className="h-9 w-9 p-0 bg-[var(--zap-primary)] text-white hover:bg-black/80 rounded-sm
                       disabled:opacity-30"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
