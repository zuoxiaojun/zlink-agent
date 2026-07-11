import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { IconSend, IconPaperclip, IconX } from "@tabler/icons-react";
import { api } from "../api/http";
import type { ContentPart, SlashCommandInfo, SlashCommandsResponse } from "../types";
import SlashCommandPopup from "./SlashCommandPopup";

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
  const isComposingRef = useRef(false);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<AttachedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [showPopup, setShowPopup] = useState(false);
  const [cursorPos, setCursorPos] = useState(0);
  const [filterText, setFilterText] = useState("");
  const [allCommands, setAllCommands] = useState<SlashCommandInfo[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (!disabled) textareaRef.current?.focus();
  }, [disabled]);

  // Fetch available slash commands once on mount
  useEffect(() => {
    let cancelled = false;
    api.get<SlashCommandsResponse>("/slash-commands")
      .then((res) => { if (!cancelled) setAllCommands(res.commands); })
      .catch(() => { /* fail silently — popup simply won't appear */ });
    return () => { cancelled = true; };
  }, []);

  // Clamp activeIndex when filtered list shrinks
  useEffect(() => {
    if (activeIndex >= filteredCommands.length) {
      setActiveIndex(Math.max(filteredCommands.length - 1, 0));
    }
  }, [filteredCommands, activeIndex]);

  const filteredCommands = useMemo(() => {
    if (!filterText) return allCommands;
    return allCommands.filter((c) => c.name.startsWith(filterText));
  }, [allCommands, filterText]);

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
    if (showPopup) {
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          if (filteredCommands.length > 0) {
            setActiveIndex((i) => Math.min(i + 1, filteredCommands.length - 1));
          }
          return;
        case "ArrowUp":
          e.preventDefault();
          if (filteredCommands.length > 0) {
            setActiveIndex((i) => Math.max(i - 1, 0));
          }
          return;
        case "Enter":
          if (!e.shiftKey && !isComposingRef.current) {
            e.preventDefault();
            if (filteredCommands.length > 0 && filteredCommands[activeIndex]) {
              handleCommandSelect(filteredCommands[activeIndex].name);
            }
          }
          return;
        case "Escape":
          e.preventDefault();
          setShowPopup(false);
          return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey && !isComposingRef.current) {
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

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    const cursor = e.target.selectionStart;
    setText(val);
    setCursorPos(cursor);

    // Detect if user is typing a slash command at the current cursor position
    const beforeCursor = val.slice(0, cursor);
    const lastWord = beforeCursor.split(/[\s\n]/).pop() || "";
    const isSlashTyping = lastWord.startsWith("/") && lastWord.length > 0;

    if (isSlashTyping) {
      const filter = lastWord.slice(1); // text after "/"
      setShowPopup(true);
      setFilterText(filter);
      setActiveIndex(0);
    } else {
      setShowPopup(false);
    }
  };

  const handleCommandSelect = (name: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const currentText = ta.value;
    const curCursor = ta.selectionStart;
    const beforeCursor = currentText.slice(0, curCursor);
    const lastSlashIndex = beforeCursor.lastIndexOf("/");
    if (lastSlashIndex === -1) return;

    const cmd = allCommands.find((c) => c.name === name);
    const replacement = cmd ? cmd.usage : `/${name}`;

    // Find the end of the current slash-word (stop at whitespace or end of string)
    const afterCursor = currentText.slice(curCursor);
    const endMatch = afterCursor.search(/[\s\n]/);
    const wordEnd = endMatch >= 0 ? curCursor + endMatch : currentText.length;

    const newText =
      currentText.slice(0, lastSlashIndex) + replacement + currentText.slice(wordEnd);
    setText(newText);
    setShowPopup(false);

    // Move cursor to end of the inserted command usage
    setTimeout(() => {
      ta.focus();
      const newCursor = lastSlashIndex + replacement.length;
      ta.setSelectionRange(newCursor, newCursor);
    }, 0);
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
        {showPopup && (
          <SlashCommandPopup
            commands={filteredCommands}
            activeIndex={activeIndex}
            onSelect={handleCommandSelect}
            onClose={() => setShowPopup(false)}
            onHover={setActiveIndex}
          />
        )}
        {files.length > 0 && (
          <div className="chat-attachments">
            {files.map((f) => (
              <div key={f.id} className="chat-attachment-item">
                <img src={f.dataUrl} alt={f.name} />
                <button className="chat-attachment-remove" onClick={() => removeFile(f.id)} type="button">
                  <IconX size={12} />
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
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => { isComposingRef.current = true; }}
            onCompositionEnd={() => { isComposingRef.current = false; }}
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
              <IconPaperclip size={16} />
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
              <IconSend size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
