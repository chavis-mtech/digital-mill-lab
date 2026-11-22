"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { BookOpen, Bot, CircleHelp, Database, History, MessageSquarePlus, SendHorizontal, ShieldAlert, ShieldCheck, Wrench } from "lucide-react";
import type { Schema } from "@dml/contracts";
import { AIWorkspaceLayout } from "@/components/layouts/layouts";
import { apiGet } from "@/lib/api/client";
import { useApiMutation, useApiQuery } from "@/lib/api/hooks";
import type { ApiRequestError } from "@/lib/api/errors";
import { useDemo } from "@/lib/demo/context";
import { useLocale, useT } from "@/lib/i18n/client";
import { formatDate, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ProvenanceBadge } from "@/components/demo/provenance-badge";
import { ErrorState, QueryState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/toast";
import { ApiText, Section, TextArea } from "@/features/maintenance/shared/ops-ui";
import { MAX_QUESTION_CHARS, citationKind, isNoData, questionProblem, readVerification, reasonKey } from "./helpers";
import messages from "./copilot.i18n";

type ChatResponse = Schema<"ChatResponse">;
type Citation = Schema<"Citation">;
type ToolCall = Schema<"ToolCall">;

type Msg =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; text: string; resp?: ChatResponse; stored?: { intent?: string | null; tool_calls?: ToolCall[]; citations?: Citation[] } }
  | { id: string; role: "error"; error: ApiRequestError | Error; question: string };

let seq = 0;
const nid = () => `m${++seq}`;

export function CopilotPage() {
  const t = useT(messages);
  const { locale } = useLocale();
  const demo = useDemo();
  const [lang, setLang] = useState<"th" | "en">(locale);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [source, setSource] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const chat = useApiMutation("/api/v1/copilot/chat", { invalidate: ["/api/v1/copilot/sessions"] });

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, chat.isPending]);

  const ask = useCallback(
    async (question: string) => {
      const problem = questionProblem(question);
      if (problem) {
        if (problem === "too_long") toast.error(t.tooLong);
        return;
      }
      const q = question.trim();
      setMsgs((m) => [...m, { id: nid(), role: "user", text: q }]);
      setDraft("");
      try {
        const resp = await chat.mutateAsync({ body: { message: q, copilot_session_id: sessionId, lang } });
        const id = nid();
        setSessionId(resp.copilot_session_id);
        setMsgs((m) => [...m, { id, role: "assistant", text: resp.answer, resp }]);
        setSelected(id);
      } catch (e) {
        setMsgs((m) => [...m, { id: nid(), role: "error", error: e instanceof Error ? e : new Error(String(e)), question: q }]);
      }
    },
    [chat, sessionId, lang, t],
  );

  function newChat() {
    setMsgs([]);
    setSessionId(null);
    setSelected(null);
  }

  const loadSession = useCallback(
    async (id: string) => {
      try {
        const d = await apiGet("/api/v1/copilot/sessions/{copilot_session_id}", { params: { path: { copilot_session_id: id } } }, demo.request);
        const loaded: Msg[] = d.messages.map((m) =>
          m.sender === "user" ? { id: nid(), role: "user" as const, text: m.content } : { id: nid(), role: "assistant" as const, text: m.content, stored: { intent: m.intent, tool_calls: m.tool_calls, citations: m.citations } },
        );
        setMsgs(loaded);
        setSessionId(d.id);
        setSelected([...loaded].reverse().find((m) => m.role === "assistant")?.id ?? null);
      } catch {
        toast.error(t.historyLoadFailed);
      }
    },
    [demo.request, t],
  );

  const selectedMsg = msgs.find((m) => m.id === selected && m.role === "assistant") as Extract<Msg, { role: "assistant" }> | undefined;
  const latestMode = [...msgs].reverse().find((m): m is Extract<Msg, { role: "assistant" }> => m.role === "assistant" && Boolean(m.resp))?.resp?.mode;
  const tools = useApiQuery("/api/v1/copilot/tools");
  const mode = latestMode ?? tools.data?.mode ?? "deterministic";
  const suggested = [t.q.oer, t.q.inspect, t.q.downtime, t.q.cut, t.q.trucks, t.q.energy, t.q.summary, t.q.priority, t.q.brief];
  const safety = [t.q.noData, t.q.control, t.q.trace, t.q.inject];

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (!chat.isPending) void ask(draft);
    }
  }

  return (
    <AIWorkspaceLayout route="/demo/ai-copilot" rail={<EvidenceRail msg={selectedMsg} onOpenSource={setSource} />} railTitle={t.evidenceTitle}>
      <div role="note" className="flex flex-col gap-2 rounded-xl border border-info/40 bg-info-soft/40 p-3 sm:flex-row sm:items-center sm:justify-between" data-tour="copilot-readonly">
        <p className="flex items-start gap-2 text-xs">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-info-fg" aria-hidden />
          <span>
            <b className="text-foreground">{t.readOnlyTitle}.</b> {t.readOnlyBody}
          </span>
        </p>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <ModeBadge mode={mode} />
          <ToggleGroup type="single" value={lang} onValueChange={(v) => v && setLang(v as "th" | "en")} aria-label={t.langLabel}>
            <ToggleGroupItem value="th" className="px-2.5 text-xs">
              {t.langTh}
            </ToggleGroupItem>
            <ToggleGroupItem value="en" className="px-2.5 text-xs">
              {t.langEn}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </div>

      <Section title={t.suggested} id="copilot-suggested">
        <div className="flex flex-wrap gap-2">
          {suggested.map((q) => (
            <Button key={q} size="sm" variant="outline" className="h-auto min-h-8 py-1.5 max-w-full shrink text-left whitespace-normal" disabled={chat.isPending} onClick={() => void ask(q)}>
              {q}
            </Button>
          ))}
        </div>
        <p className="mt-1 text-2xs font-semibold text-muted-foreground uppercase">{t.safetyChecks}</p>
        <div className="flex flex-wrap gap-2">
          {safety.map((q) => (
            <Button key={q} size="sm" variant="ghost" className="h-auto min-h-8 border border-dashed border-border-strong py-1.5 max-w-full shrink text-left whitespace-normal" disabled={chat.isPending} onClick={() => void ask(q)}>
              {q}
            </Button>
          ))}
        </div>
      </Section>

      <section aria-label={t.copilot} className="flex min-w-0 flex-col gap-3 rounded-xl border border-border bg-surface p-4 shadow-xs">
        <div className="flex items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Bot className="size-4" aria-hidden /> {t.copilot}
          </h2>
          <Button size="xs" variant="ghost" onClick={newChat} disabled={msgs.length === 0}>
            <MessageSquarePlus aria-hidden /> {t.newChat}
          </Button>
        </div>
        <div ref={listRef} role="log" aria-live="polite" aria-label={t.copilot} tabIndex={0} className="flex max-h-[28rem] min-h-40 flex-col gap-3 overflow-y-auto rounded-lg border border-border bg-background p-3 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          {msgs.length === 0 ? <p className="m-auto max-w-sm text-center text-sm text-muted-foreground">{t.empty}</p> : null}
          {msgs.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="ml-auto max-w-[85%] rounded-xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
                <p className="sr-only">{t.you}</p>
                <p className="whitespace-pre-wrap">{m.text}</p>
              </div>
            ) : m.role === "error" ? (
              <div key={m.id} className="max-w-[90%]">
                <ErrorState error={m.error} compact onRetry={() => void ask(m.question)} />
              </div>
            ) : (
              <AssistantBubble key={m.id} msg={m} active={m.id === selected} onSelect={() => setSelected(m.id)} onAsk={(q) => void ask(q)} onOpenSource={setSource} busy={chat.isPending} />
            ),
          )}
          {chat.isPending ? (
            <div role="status" className="max-w-[85%] rounded-xl rounded-bl-sm border border-border bg-surface px-3 py-2 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <span className="size-2 animate-pulse rounded-full bg-accent" aria-hidden /> {t.sending}
              </span>
            </div>
          ) : null}
        </div>
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!chat.isPending) void ask(draft);
          }}
        >
          <label htmlFor="copilot-input" className="sr-only">
            {t.inputLabel}
          </label>
          <TextArea id="copilot-input" value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={onKey} placeholder={t.placeholder} maxLength={MAX_QUESTION_CHARS + 200} rows={2} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-2xs text-muted-foreground">
              {t.inputHint} · <span className="tabular">{draft.length}/{MAX_QUESTION_CHARS}</span>
            </p>
            <Button type="submit" variant="accent" disabled={chat.isPending || questionProblem(draft) !== null}>
              <SendHorizontal aria-hidden /> {chat.isPending ? t.sending : t.send}
            </Button>
          </div>
        </form>
      </section>

      <HistorySection activeId={sessionId} onOpen={(id) => void loadSession(id)} />
      <ToolCatalog />
      <SourceDialog refId={source} lang={lang} onClose={() => setSource(null)} />
    </AIWorkspaceLayout>
  );
}

function ModeBadge({ mode }: { mode: "deterministic" | "llm" }) {
  const t = useT(messages);
  const label = mode === "llm" ? t.modeLlm : t.modeDeterministic;
  const tip = mode === "llm" ? t.modeLlmTip : t.modeDeterministicTip;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="inline-flex rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none" data-copilot-mode={mode}>
          <Badge tone={mode === "llm" ? "maintenance" : "accent"}>
            {t.modeLabel}: {label}
          </Badge>
        </span>
      </TooltipTrigger>
      <TooltipContent>{tip}</TooltipContent>
    </Tooltip>
  );
}

function AssistantBubble({
  msg,
  active,
  onSelect,
  onAsk,
  onOpenSource,
  busy,
}: {
  msg: Extract<Msg, { role: "assistant" }>;
  active: boolean;
  onSelect: () => void;
  onAsk: (q: string) => void;
  onOpenSource: (ref: string) => void;
  busy: boolean;
}) {
  const t = useT(messages);
  const r = msg.resp;
  const refused = Boolean(r?.refused);
  const noData = r ? isNoData(r) : false;
  const citations = r?.citations ?? msg.stored?.citations ?? [];
  const reasons = t.reason as Record<string, string>;
  return (
    <article
      data-refused={refused || undefined}
      data-no-data={noData || undefined}
      className={cn("max-w-[92%] rounded-xl rounded-bl-sm border bg-surface px-3 py-2.5 text-sm", active ? "border-accent" : "border-border", refused && "border-warning/60 bg-warning-soft/40")}
    >
      <p className="sr-only">{t.copilot}</p>
      {refused ? (
        <div className="mb-1.5 flex items-start gap-2 text-xs">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warning-fg" aria-hidden />
          <div>
            <p className="font-semibold text-foreground">{t.refusedTitle}</p>
            <p className="text-muted-foreground">{reasons[reasonKey(r?.refusal_reason)]}</p>
          </div>
        </div>
      ) : null}
      {noData ? (
        <div className="mb-1.5 flex items-start gap-2 text-xs">
          <CircleHelp className="mt-0.5 size-4 shrink-0 text-info-fg" aria-hidden />
          <div>
            <p className="font-semibold text-foreground">{t.noDataTitle}</p>
            <p className="text-muted-foreground">{t.noDataBody}</p>
          </div>
        </div>
      ) : null}
      <p lang={r?.lang} className="leading-relaxed whitespace-pre-wrap">
        {msg.text}
      </p>
      {r?.llm_answer_rejected ? <p className="mt-1.5 text-xs text-warning-fg">{t.llmRejected}</p> : null}
      {r?.uncertainty && !noData ? (
        <p className="mt-1.5 text-xs text-muted-foreground">
          <b className="text-foreground">{t.uncertainty}:</b> <ApiText>{r.uncertainty}</ApiText>
        </p>
      ) : null}
      {r?.assumptions && r.assumptions.length > 0 ? (
        <details className="mt-1.5 text-xs">
          <summary className="cursor-pointer text-accent-text">
            {t.assumptions} ({r.assumptions.length})
          </summary>
          <ul className="mt-1 list-disc pl-5 text-muted-foreground">
            {r.assumptions.map((a) => (
              <li key={a} lang="en">
                {a}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {citations.length > 0 ? (
        <div className="mt-2">
          <p className="text-2xs font-semibold text-muted-foreground uppercase">{t.citations}</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {citations.map((c) =>
              citationKind(c.ref) === "document" ? (
                <li key={c.ref}>
                  <button type="button" onClick={() => onOpenSource(c.ref)} title={c.snippet ?? undefined} className="inline-flex max-w-72 items-center gap-1 rounded-md border border-border-strong bg-surface px-2 py-1 text-left text-2xs hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
                    <BookOpen className="size-3 shrink-0" aria-hidden />
                    <span className="sr-only">{t.openSource}: </span>
                    <span className="truncate">{c.title}{c.heading ? ` › ${c.heading}` : ""}</span>
                  </button>
                </li>
              ) : (
                <li key={c.ref}>
                  <span title={c.snippet ?? undefined} className="inline-flex max-w-72 items-center gap-1 rounded-md border border-dashed border-border-strong px-2 py-1 text-2xs text-muted-foreground">
                    <Database className="size-3 shrink-0" aria-hidden />
                    <span className="truncate font-mono">{c.ref.replace(/^tool:/, "")}</span>
                  </span>
                </li>
              ),
            )}
          </ul>
        </div>
      ) : null}
      {r?.suggested_followups && r.suggested_followups.length > 0 ? (
        <div className="mt-2">
          <p className="text-2xs font-semibold text-muted-foreground uppercase">{t.followups}</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {r.suggested_followups.map((f) => (
              <Button key={f} size="xs" variant="outline" className="h-auto py-1 max-w-full shrink text-left whitespace-normal" disabled={busy} onClick={() => onAsk(f)}>
                {f}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-border pt-2">
        {r ? <ProvenanceBadge provenance={r.provenance} /> : null}
        {r ? <Badge tone="outline">{r.mode}</Badge> : null}
        {(r?.intent ?? msg.stored?.intent) ? (
          <Badge tone="outline">
            {t.intent}: <span className="font-mono">{r?.intent ?? msg.stored?.intent}</span>
          </Badge>
        ) : null}
        <Button size="xs" variant={active ? "secondary" : "ghost"} className="ml-auto" onClick={onSelect} aria-pressed={active}>
          <Wrench aria-hidden /> {active ? t.evidenceSelected : t.selectForEvidence}
        </Button>
      </div>
    </article>
  );
}

function EvidenceRail({ msg, onOpenSource }: { msg?: Extract<Msg, { role: "assistant" }>; onOpenSource: (ref: string) => void }) {
  const t = useT(messages);
  const { locale } = useLocale();
  if (!msg) return <p className="rounded-xl border border-dashed border-border-strong p-4 text-xs text-muted-foreground">{t.evidenceNone}</p>;
  const r = msg.resp;
  const calls = r?.tool_calls ?? msg.stored?.tool_calls ?? [];
  const ver = readVerification(r?.verification as never);
  const citations = r?.citations ?? msg.stored?.citations ?? [];
  return (
    <div className="flex flex-col gap-4">
      <section className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4" aria-label={t.tools}>
        <h3 className="text-sm font-semibold">{t.tools}</h3>
        {calls.length === 0 ? <p className="text-xs text-muted-foreground">—</p> : null}
        <ul className="flex flex-col gap-2">
          {calls.map((c, i) => (
            <li key={`${c.tool}-${i}`} className="rounded-lg border border-border p-2.5 text-xs">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-mono font-semibold">{c.tool}</span>
                <Badge tone={c.allowed ? "success" : "critical"}>{c.allowed ? t.toolAllowed : t.toolDenied}</Badge>
                <span className="text-muted-foreground">{c.status}</span>
                {c.duration_ms != null ? <span className="tabular ml-auto text-muted-foreground">{t.toolMs(c.duration_ms)}</span> : null}
              </div>
              {Object.keys(c.arguments ?? {}).length > 0 ? (
                <p className="mt-1 font-mono text-2xs break-all text-muted-foreground">
                  {t.toolArgs}: {JSON.stringify(c.arguments)}
                </p>
              ) : null}
              {c.result_summary ? (
                <p className="mt-0.5 text-muted-foreground" lang="en">
                  {c.result_summary}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      {r?.evidence?.map((e, i) => (
        <section key={`${e.tool}-${i}`} className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4" aria-label={`${t.facts}: ${e.tool}`}>
          <div className="flex flex-wrap items-center gap-1.5">
            <h3 className="font-mono text-sm font-semibold">{e.tool}</h3>
            {e.provenance ? <ProvenanceBadge provenance={e.provenance} /> : null}
          </div>
          {e.as_of ? (
            <p className="text-2xs text-muted-foreground">
              {t.evidenceAsOf}: <span className="tabular">{formatDate(e.as_of, locale, "datetime")}</span> · {t.digest}: <span className="font-mono">{e.result_digest}</span>
            </p>
          ) : null}
          {e.facts && e.facts.length > 0 ? (
            <div className="max-h-72 overflow-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={`${t.facts}: ${e.tool}`}>
              <table className="tabular w-full border-collapse text-left text-xs">
                <caption className="sr-only">{t.facts}</caption>
                <thead className="sticky top-0 bg-surface-2 text-muted-foreground">
                  <tr>
                    <th scope="col" className="border-b border-border px-2 py-1.5 font-semibold">
                      {t.factLabel}
                    </th>
                    <th scope="col" className="border-b border-border px-2 py-1.5 text-right font-semibold">
                      {t.factValue}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {e.facts.map((f) => (
                    <tr key={f.key} className="border-b border-border last:border-0 align-top">
                      <th scope="row" className="px-2 py-1.5 text-left font-normal" lang="en">
                        {f.label}
                      </th>
                      <td className="px-2 py-1.5 text-right font-semibold whitespace-nowrap">
                        {formatNumber(f.value, locale)} {f.unit ?? ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {e.assumptions && e.assumptions.length > 0 ? (
            <ul className="list-disc pl-5 text-2xs text-muted-foreground">
              {e.assumptions.map((a) => (
                <li key={a} lang="en">
                  {a}
                </li>
              ))}
            </ul>
          ) : null}
          {e.limits && e.limits.length > 0 ? (
            <p className="text-2xs text-muted-foreground">
              <b>{t.limits}:</b> <span lang="en">{e.limits.join(" · ")}</span>
            </p>
          ) : null}
        </section>
      ))}

      {r?.verification ? (
        <section className="flex flex-col gap-1.5 rounded-xl border border-border bg-surface p-4 text-xs" aria-label={t.verification}>
          <h3 className="text-sm font-semibold">{t.verification}</h3>
          {ver.checked != null && ver.checked > 0 && ver.supported != null ? (
            <p>
              <Badge tone={ver.unsupported.length === 0 ? "success" : "warning"}>{t.verified(ver.supported, ver.checked)}</Badge>
            </p>
          ) : null}
          {ver.unsupported.length > 0 ? (
            <p>
              <b>{t.unsupported}:</b> <span className="font-mono">{ver.unsupported.join(", ")}</span>
            </p>
          ) : null}
          {ver.causal.length > 0 ? (
            <p>
              <b>{t.causalFlags}:</b> {ver.causal.join(", ")}
            </p>
          ) : null}
          {r.safety_flags && r.safety_flags.length > 0 ? (
            <p>
              <b>{t.safetyFlags}:</b> <span className="font-mono">{r.safety_flags.join(", ")}</span>
            </p>
          ) : null}
          {r.limits && r.limits.length > 0 ? (
            <ul className="list-disc pl-5 text-muted-foreground">
              {r.limits.map((l) => (
                <li key={l} lang="en">
                  {l}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {citations.length > 0 ? (
        <section className="flex flex-col gap-1.5 rounded-xl border border-border bg-surface p-4 text-xs" aria-label={t.citations}>
          <h3 className="text-sm font-semibold">{t.citations}</h3>
          <ul className="flex flex-col gap-1.5">
            {citations.map((c) => (
              <li key={c.ref} className="rounded-lg border border-border p-2">
                <p className="flex items-center gap-1.5 font-medium">
                  <Badge tone="outline">{citationKind(c.ref) === "document" ? t.citeDoc : t.citeData}</Badge>
                  <span lang="en" className="min-w-0 truncate">
                    {c.title}
                  </span>
                </p>
                {c.snippet ? (
                  <p lang="en" className="mt-0.5 line-clamp-3 text-muted-foreground">
                    {c.snippet}
                  </p>
                ) : null}
                {citationKind(c.ref) === "document" ? (
                  <Button size="xs" variant="link" onClick={() => onOpenSource(c.ref)}>
                    <BookOpen aria-hidden /> {t.openSource}
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function SourceDialog({ refId, lang, onClose }: { refId: string | null; lang: "th" | "en"; onClose: () => void }) {
  const t = useT(messages);
  const q = useApiQuery("/api/v1/copilot/sources/{ref}", { params: { path: { ref: refId ?? "" } } }, { enabled: refId !== null, withClock: false });
  const [full, setFull] = useState(false);
  const slug = q.data?.document_slug;
  const doc = useApiQuery("/api/v1/kb/documents/{slug}", { params: { path: { slug: slug ?? "" }, query: { lang } } }, { enabled: full && Boolean(slug), withClock: false });
  return (
    <Dialog
      open={refId !== null}
      onOpenChange={(o) => {
        if (!o) {
          setFull(false);
          onClose();
        }
      }}
    >
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto" closeLabel="Close">
        <DialogTitle>{t.sourceTitle}</DialogTitle>
        <DialogDescription>{t.sourceKb}</DialogDescription>
        <QueryState query={q} compact>
          {(d) => (
            <div className="flex flex-col gap-2 text-sm">
              <p className="font-semibold" lang="en">
                {d.document_title}
              </p>
              {d.heading ? (
                <p className="text-xs text-muted-foreground">
                  {t.sourceHeading}: <span lang="en">{d.heading}</span>
                </p>
              ) : null}
              <p lang="en" className="rounded-lg bg-surface-2 p-3 text-xs leading-relaxed whitespace-pre-wrap">
                {d.text}
              </p>
              {d.notice ? (
                <p className="text-2xs text-muted-foreground" lang="en">
                  {d.notice}
                </p>
              ) : null}
              <Button size="sm" variant="outline" className="self-start" onClick={() => setFull((v) => !v)} aria-expanded={full}>
                {t.sourceFull}
              </Button>
              {full ? (
                <QueryState query={doc} compact>
                  {(dd) => (
                    <pre lang={dd.lang} className="max-h-80 overflow-auto rounded-lg border border-border p-3 text-xs leading-relaxed whitespace-pre-wrap">
                      {dd.body_md}
                    </pre>
                  )}
                </QueryState>
              ) : null}
            </div>
          )}
        </QueryState>
      </DialogContent>
    </Dialog>
  );
}

function HistorySection({ activeId, onOpen }: { activeId: string | null; onOpen: (id: string) => void }) {
  const t = useT(messages);
  const { locale } = useLocale();
  const q = useApiQuery("/api/v1/copilot/sessions");
  return (
    <Section title={t.history} id="copilot-history">
      <QueryState query={q} isEmpty={(d) => d.items.length === 0} empty={<p className="text-xs text-muted-foreground">{t.historyNone}</p>} compact>
        {(d) => (
          <ul className="flex max-h-56 flex-col gap-1.5 overflow-y-auto">
            {d.items.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => onOpen(s.id)}
                  aria-pressed={s.id === activeId}
                  className={cn("flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", s.id === activeId ? "border-accent bg-accent-soft/40" : "border-border hover:bg-surface-2")}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <History className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="truncate" lang={undefined}>
                      {s.title ?? s.id}
                    </span>
                  </span>
                  <span className="tabular shrink-0 text-muted-foreground">
                    {t.historyMessages(s.message_count ?? 0)} · {formatDate(s.created_at, locale, "datetime")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </Section>
  );
}

function ToolCatalog() {
  const t = useT(messages);
  const q = useApiQuery("/api/v1/copilot/tools");
  return (
    <Section title={t.toolsCatalog} description={t.toolsCatalogNote} id="copilot-tools">
      <QueryState query={q} compact>
        {(d) => (
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {d.tools.map((tool) => (
              <li key={tool.name} className={cn("rounded-lg border p-2.5 text-xs", tool.allowed_for_role ? "border-border" : "border-dashed border-border-strong bg-surface-2/50")}>
                <p className="flex flex-wrap items-center gap-1.5">
                  <span className="font-mono font-semibold">{tool.name}</span>
                  {tool.read_only !== false ? <Badge tone="outline">{t.toolReadOnly}</Badge> : null}
                  {!tool.allowed_for_role ? <Badge tone="warning">{t.toolNotAllowed}</Badge> : null}
                </p>
                <p className="mt-0.5 text-muted-foreground" lang="en">
                  {tool.description}
                </p>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </Section>
  );
}
