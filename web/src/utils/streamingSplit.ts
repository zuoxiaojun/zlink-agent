export interface StreamingSplit {
  closed: string;
  tail: string;
}

export function splitStreamingText(text: string): StreamingSplit {
  const normalized = text.replace(/\r\n/g, "\n");
  const segments = normalized.split("\n\n").filter((s) => s.length > 0);
  if (segments.length === 0) return { closed: "", tail: "" };

  const isListSegment = (s: string) => /^\s*(?:[-*+]|\d+\.)\s/.test(s);

  let openFence = false;
  let lastClosable = -1;
  for (let i = 0; i < segments.length - 1; i++) {
    const seg = segments[i];
    const next = segments[i + 1];
    const backtickCount = (seg.match(/`/g) || []).length;
    openFence = openFence !== (backtickCount % 2 === 1);
    const closable =
      !openFence && !/^\s/.test(next) && !(isListSegment(seg) && isListSegment(next));
    if (closable) lastClosable = i;
  }

  const closed = lastClosable >= 0 ? segments.slice(0, lastClosable + 1).join("\n\n") : "";
  const tail = segments.slice(lastClosable + 1).join("\n\n");
  return { closed, tail };
}
