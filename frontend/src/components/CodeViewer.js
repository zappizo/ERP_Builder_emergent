import { useEffect, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileCode, FolderOpen, Copy, CheckCircle2 } from "lucide-react";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import js from "react-syntax-highlighter/dist/esm/languages/hljs/javascript";
import jsonLang from "react-syntax-highlighter/dist/esm/languages/hljs/json";
import markdown from "react-syntax-highlighter/dist/esm/languages/hljs/markdown";
import python from "react-syntax-highlighter/dist/esm/languages/hljs/python";
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs";

SyntaxHighlighter.registerLanguage("javascript", js);
SyntaxHighlighter.registerLanguage("jsx", js);
SyntaxHighlighter.registerLanguage("json", jsonLang);
SyntaxHighlighter.registerLanguage("markdown", markdown);
SyntaxHighlighter.registerLanguage("python", python);

function getLanguage(path) {
  if (!path) return "javascript";
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".md")) return "markdown";
  if (path.endsWith(".jsx") || path.endsWith(".tsx") || path.endsWith(".js") || path.endsWith(".ts")) return "javascript";
  return "javascript";
}

export default function CodeViewer({ files }) {
  const [selected, setSelected] = useState(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (files?.length && selected >= files.length) {
      setSelected(0);
    }
  }, [files, selected]);

  if (!files?.length) return null;

  const file = files[selected] || files[0];
  if (!file) return null;

  function handleCopy() {
    navigator.clipboard.writeText(file.content || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex border border-[var(--zap-border)] bg-white rounded-sm overflow-hidden h-[calc(100vh-220px)]" data-testid="code-viewer">
      {/* File Tree */}
      <div className="w-56 border-r border-[var(--zap-border)] shrink-0">
        <div className="px-3 py-2 border-b border-[var(--zap-border)] bg-[var(--zap-bg)]">
          <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--zap-text-muted)] uppercase tracking-[0.1em]">
            <FolderOpen className="w-3 h-3" /> Files
          </div>
        </div>
        <ScrollArea className="h-full">
          <div className="py-1">
            {files.map((f, i) => (
              <button
                key={i}
                data-testid={`file-select-${i}`}
                onClick={() => setSelected(i)}
                className={`w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 transition-colors ${
                  i === selected
                    ? "bg-[var(--zap-accent)]/5 text-[var(--zap-accent)] font-medium"
                    : "text-[var(--zap-text-body)] hover:bg-[var(--zap-bg)]"
                }`}
              >
                <FileCode className="w-3 h-3 shrink-0" />
                <span className="truncate" style={{ fontFamily: 'var(--font-mono)' }}>{f.path}</span>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Code Display */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="px-3 py-2 border-b border-[var(--zap-border)] bg-[var(--zap-bg)] flex items-center justify-between">
          <span className="text-xs font-medium" style={{ fontFamily: 'var(--font-mono)' }}>{file.path}</span>
          <button
            data-testid="copy-code-btn"
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs text-[var(--zap-text-muted)] hover:text-[var(--zap-text-heading)] transition-colors"
          >
            {copied ? <CheckCircle2 className="w-3 h-3 text-[var(--zap-success)]" /> : <Copy className="w-3 h-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <div className="flex-1 overflow-auto bg-[#0A0A0A]">
          <SyntaxHighlighter
            language={getLanguage(file.path)}
            style={atomOneDark}
            customStyle={{
              margin: 0,
              padding: "16px",
              background: "#0A0A0A",
              fontSize: "13px",
              fontFamily: "var(--font-mono)",
              lineHeight: "1.6",
              minHeight: "100%",
            }}
            showLineNumbers
            lineNumberStyle={{ color: "#4B5563", fontSize: "11px", paddingRight: "12px" }}
          >
            {file.content || "// No content"}
          </SyntaxHighlighter>
        </div>
      </div>
    </div>
  );
}
