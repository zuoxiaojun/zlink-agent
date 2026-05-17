import { useRef, useEffect, useState, useCallback } from "react";
import { Send, Paperclip, X } from "lucide-react";
import type { ContentPart } from "../types";

interface AttachedFile {
  id: string;
  name: string;
  dataUrl: string;
}

interface Props {
  onSubmit: (content: string | ContentPart[]) => void;
  disabled: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSubmit, disabled, placeholder }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<AttachedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    if (!disabled) textareaRef.current?.focus();
  }, [disabled]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed && files.length === 0) return;
    if (disabled) return;

    if (files.length === 0) {
      onSubmit(trimmed);
    } else {
      const parts: ContentPart[] = [];
      if (trimmed) parts.push({ type: "text", text: trimmed });
      for (const f of files) {
        parts.push({ type: "image_url", image_url: { url: f.dataUrl } });
      }
      onSubmit(parts);
    }

    setText("");
    setFiles([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const addFile = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      setFiles((prev) => [
        ...prev,
        { id: `${Date.now()}-${Math.random()}`, name: file.name, dataUrl: reader.result as string },
      ]);
    };
    reader.readAsDataURL(file);
  }, []);

  const addFiles = useCallback(
    (fileList: FileList) => {
      for (let i = 0; i < fileList.length; i++) addFile(fileList[i]);
    },
    [addFile],
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(e.target.files);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      const file = items[i].getAsFile();
      if (file && file.type.startsWith("image/")) {
        e.preventDefault();
        addFile(file);
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer?.files) addFiles(e.dataTransfer.files);
  };

  const removeFile = (id: string) => setFiles((prev) => prev.filter((f) => f.id !== id));

  const canSend = !disabled && (text.trim().length > 0 || files.length > 0);

  return (
    <div className="chat-input-area" onPaste={handlePaste}>
      <div
        className={`chat-input-wrapper${dragOver ? " drag-over" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {files.length > 0 && (
          <div className="chat-attachments">
            {files.map((f) => (
              <div key={f.id} className="chat-attachment-item">
                <img src={f.dataUrl} alt={f.name} />
                <button className="chat-attachment-remove" onClick={() => removeFile(f.id)} type="button">
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="chat-input-row">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || "输入你的问题，Enter 发送，Shift+Enter 换行..."}
            disabled={disabled}
            rows={1}
          />

          <div className="chat-input-actions">
            <button
              type="button"
              className="chat-attach-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
              title="添加图片"
            >
              <Paperclip size={16} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={handleFileSelect}
              style={{ display: "none" }}
            />
            <button className="chat-send-btn" type="button" onClick={handleSubmit} disabled={!canSend}>
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
