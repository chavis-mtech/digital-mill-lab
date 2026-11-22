import { describe, expect, it } from "vitest";
import { inlineText, parseInline, parseMarkdown, safeHref, slugify, tocOf } from "./markdown";

describe("inline", () => {
  it("parses code, bold, italic, strike, links and escapes", () => {
    const i = parseInline("a `x|y` **b** *c* ~~d~~ [l](https://e.com) \\*lit\\*");
    expect(i.map((n) => n.t)).toEqual(["text", "code", "text", "strong", "text", "em", "text", "del", "text", "link", "text"]);
    expect(inlineText(i)).toContain("*lit*");
  });
  it("shows images as alt text only and never as a link", () => {
    expect(parseInline("![diagram](http://x/y.png)")).toEqual([{ t: "text", v: "diagram" }]);
  });
  it("does not parse markup inside code spans", () => {
    expect(parseInline("`**no**`")).toEqual([{ t: "code", v: "**no**" }]);
  });
});

describe("links are sanitised", () => {
  it("allows http(s), mailto and anchors", () => {
    expect(safeHref("https://a.b/c")?.kind).toBe("external");
    expect(safeHref("mailto:a@b.c")?.kind).toBe("mailto");
    expect(safeHref("#section-1")?.kind).toBe("anchor");
  });
  it("blocks script-like and unmapped relative targets", () => {
    expect(safeHref("javascript:alert(1)")).toBeNull();
    expect(safeHref(" JavaScript:alert(1)")).toBeNull();
    expect(safeHref("data:text/html;base64,AAAA")).toBeNull();
    expect(safeHref("file:///etc/passwd")).toBeNull();
    expect(safeHref("../../etc/passwd")).toBeNull();
    expect(safeHref("#a b")).toBeNull();
  });
  it("maps relative document links through the callback", () => {
    expect(safeHref("SYSTEM_ARCHITECTURE.md", (r) => (r.endsWith("SYSTEM_ARCHITECTURE.md") ? "/docs/architecture" : null))).toEqual({ kind: "internal", href: "/docs/architecture" });
  });
});

describe("blocks", () => {
  const md = [
    "# Title",
    "",
    "Intro paragraph",
    "continues here.",
    "",
    "## Section *one*",
    "",
    "| Name | Qty |",
    "|:-----|----:|",
    "| a `x\\|y` | 1 |",
    "| b | 2 |",
    "",
    "- item 1",
    "  - nested a",
    "  - nested b",
    "- [x] done",
    "- [ ] todo",
    "",
    "1. first",
    "2. second",
    "",
    "> quoted",
    "",
    "```mermaid",
    "graph TD; A-->B",
    "```",
    "",
    "---",
    "## Section *one*",
  ].join("\n");
  const blocks = parseMarkdown(md);
  it("builds headings with unique anchors and a TOC", () => {
    expect(blocks[0]).toMatchObject({ t: "heading", level: 1, id: "title" });
    expect(tocOf(blocks)).toEqual([
      { id: "section-one", label: "Section one", level: 2 },
      { id: "section-one-1", label: "Section one", level: 2 },
    ]);
  });
  it("joins wrapped paragraph lines", () => {
    const p = blocks[1];
    expect(p?.t === "p" && inlineText(p.c)).toBe("Intro paragraph continues here.");
  });
  it("parses GFM tables with alignment and escaped pipes", () => {
    const t = blocks.find((b) => b.t === "table");
    expect(t).toMatchObject({ t: "table", align: ["left", "right"] });
    if (t?.t === "table") {
      expect(t.rows).toHaveLength(2);
      expect(inlineText(t.rows[0]![0]!)).toBe("a x|y");
    }
  });
  it("parses nested and task lists", () => {
    const l = blocks.find((b) => b.t === "list");
    expect(l?.t === "list" && l.items.length).toBe(3);
    if (l?.t === "list") {
      expect(l.items[0]!.c.some((b) => b.t === "list")).toBe(true);
      expect(l.items[1]!.task).toBe(true);
      expect(l.items[2]!.task).toBe(false);
    }
  });
  it("keeps fenced code verbatim (mermaid is just code) and handles quotes, rules and ordered lists", () => {
    expect(blocks.find((b) => b.t === "code")).toEqual({ t: "code", lang: "mermaid", v: "graph TD; A-->B" });
    expect(blocks.some((b) => b.t === "quote")).toBe(true);
    expect(blocks.some((b) => b.t === "hr")).toBe(true);
    expect(blocks.some((b) => b.t === "list" && b.ordered && b.start === 1)).toBe(true);
  });
  it("shows raw HTML as text, never as elements, and drops HTML comments", () => {
    const b = parseMarkdown("<script>alert(1)</script>\n\n<!-- note -->\n\ntext");
    expect(b[0]).toMatchObject({ t: "p" });
    expect(JSON.stringify(b)).toContain("<script>");
    expect(b).toHaveLength(2);
  });
  it("slugify de-duplicates", () => {
    const seen = new Map<string, number>();
    expect([slugify("A b", seen), slugify("A b", seen), slugify("???", seen)]).toEqual(["a-b", "a-b-1", "section"]);
  });
});
