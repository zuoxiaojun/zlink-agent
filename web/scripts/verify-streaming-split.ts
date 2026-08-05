// splitStreamingText 独立验证脚本（项目无前端测试框架，Node >= 23.6 原生执行 .ts）
// 运行: node scripts/verify-streaming-split.ts   （工作目录 web/）
import { splitStreamingText } from "../src/utils/streamingSplit.ts";

function check(input: string, expectedClosed: string, expectedTail: string, label: string): void {
  const { closed, tail } = splitStreamingText(input);
  if (closed !== expectedClosed || tail !== expectedTail) {
    console.error(`FAIL ${label}`);
    console.error(`  input:    ${JSON.stringify(input)}`);
    console.error(`  closed:   ${JSON.stringify(closed)}   (expected ${JSON.stringify(expectedClosed)})`);
    console.error(`  tail:     ${JSON.stringify(tail)}   (expected ${JSON.stringify(expectedTail)})`);
    throw new Error(`verification failed: ${label}`);
  }
  console.log(`PASS ${label}`);
}

check("", "", "", "empty text");
check("p1\n\np2\n\np3", "p1\n\np2", "p3", "plain paragraphs freeze on next segment");
check("p1", "", "p1", "last segment never closes");
check("para\n\n", "", "para", "trailing blank line filtered, para stays in tail");
check("p1\r\n\r\np2", "p1", "p2", "CRLF normalized");
check("```python\n\ncode\n\n```", "", "```python\n\ncode\n\n```", "open fence keeps all in tail");
check("```python\n\ncode\n\n```\n\nnext", "```python\n\ncode\n\n```", "next", "fenced block freezes when following segment arrives");
check("- a\n\n- b\n\n- c", "", "- a\n\n- b\n\n- c", "consecutive list items stay in tail");
check("- a\n\n- b\n\n- c\n\npara", "- a\n\n- b\n\n- c", "para", "list run freezes when non-list segment arrives");
check("- item\n\n  continuation", "", "- item\n\n  continuation", "indented continuation keeps list item in tail");
check("- item1\n\n  continuation", "", "- item1\n\n  continuation", "blank line inside list item keeps both in tail");
check("a `b\n\nc` d", "", "a `b\n\nc` d", "inline code spanning segments stays in tail");
check("| a | b |\n|---|--|\n| 1 | 2 |", "", "| a | b |\n|---|--|\n| 1 | 2 |", "GFM table is a single segment (never split)");
check("- a\n\npara", "- a", "para", "single list item freezes when non-list follows");
check("p1\n\n```python", "p1", "```python", "paragraph freezes, open fence stays in tail");
check("p1\n\np2\n\n```python\n\ncode", "p1\n\np2", "```python\n\ncode", "paragraphs freeze up to the fence");
console.log("Done");
