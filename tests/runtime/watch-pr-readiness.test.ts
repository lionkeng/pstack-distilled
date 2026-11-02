import { describe, expect, it } from "bun:test";
import {
  readSnapshot,
  runQueued,
  runSimple,
  selectTierMajorStackDecision,
} from "../../skills/poteto-mode/scripts/watch-pr/policy.ts";
import { renderJson, renderPretty, renderStatusTable } from "../../skills/poteto-mode/scripts/watch-pr/render.ts";
import {
  fakeReader,
  failedCheck,
  passingCheck,
  pendingCheck,
} from "../../skills/poteto-mode/scripts/watch-pr/fakes.test-helper.ts";
import { parsePrNumber } from "../../skills/poteto-mode/scripts/watch-pr/types.ts";
import type {
  Check,
  GitHubReader,
  NonEmpty,
  PrContext,
  ProgressVerdict,
  PullRequestFacts,
  WatchMode,
} from "../../skills/poteto-mode/scripts/watch-pr/types.ts";

const context = (number: number): PrContext => ({ owner: "owner", repo: "repo", number: parsePrNumber(number) });
const options = { interval: 1, sweepInterval: 2, timeout: 2, maxQueryErrors: 2, allowDraft: false };
const unknown = { mergeable: "UNKNOWN", mergeStateStatus: "UNKNOWN" } satisfies Partial<PullRequestFacts>;

async function run(
  mode: WatchMode,
  facts: (pr: PrContext, tick: number) => Partial<PullRequestFacts>,
  contexts: NonEmpty<PrContext> = [context(1)],
  checks: readonly Check[] = [passingCheck()],
) {
  let tick = 0;
  const base = fakeReader({ fastPath: { kind: "checks", checks } });
  const reader: GitHubReader = {
    ...base,
    async pullRequest(pr) { return { ...await base.pullRequest(pr), ...facts(pr, tick) }; },
  };
  const emitted: ProgressVerdict[] = [];
  const dependencies = {
    reader,
    clock: { now: () => tick, observedAt: () => new Date(tick * 1000).toISOString(), async sleep(seconds: number) { tick += seconds; } },
    emit: (event: ProgressVerdict) => emitted.push(event),
  };
  const terminal = mode === "queued-stack"
    ? await runQueued({ dependencies, contexts, options })
    : await runSimple({ dependencies, contexts, options, mode, statusOnly: false });
  return { emitted, terminal };
}

for (const mode of ["single", "stack", "queued-stack"] as const) {
  describe(`${mode} mergeability`, () => {
    for (const facts of [unknown, { mergeable: "UNKNOWN" as const }, { mergeStateStatus: "UNKNOWN" as const }]) {
      it(`waits and times out on ${JSON.stringify(facts)}`, async () => {
        const { emitted, terminal } = await run(mode, () => facts);
        expect(emitted).toContainEqual(expect.objectContaining({
          kind: "WAITING", terminal: false, frontier: context(1), reason: { kind: "mergeability-unknown" },
        }));
        expect(terminal).toMatchObject({ kind: "TIMEOUT", exitCode: 5, reason: { kind: "mergeability-unknown", frontier: context(1) } });
        expect(emitted.some((event) => event.kind === "WAITING" && event.reason.kind === "merge-queue")).toBe(false);
        expect(renderPretty(terminal)).toContain("mergeability remains unknown");
        for (const event of [...emitted, terminal]) expect(JSON.parse(renderJson(event)).schemaVersion).toBe(2);
      });
    }

    it("blocks a behind base even when checks pass", async () => {
      const { terminal } = await run(mode, () => ({ mergeStateStatus: "BEHIND" }));
      expect(terminal).toMatchObject({ kind: "BLOCKER", exitCode: 6, blocker: { kind: "merge-gate", reason: "base-behind", pr: context(1) } });
      expect(renderPretty(terminal)).toContain("update the branch with its base");
    });

    it("keeps conflicts above unknown facts and CI failure", async () => {
      const { terminal } = await run(mode, () => ({ mergeable: "CONFLICTING", mergeStateStatus: "UNKNOWN" }), [context(1)], [failedCheck()]);
      expect(terminal).toMatchObject({ kind: "BLOCKER", exitCode: 2, blocker: { kind: "merge-conflicts" } });
    });

    it("keeps failed checks above an unknown wait", async () => {
      const { terminal } = await run(mode, () => unknown, [context(1)], [failedCheck()]);
      expect(terminal).toMatchObject({ kind: "BLOCKER", exitCode: 4, blocker: { kind: "failing-checks" } });
    });

    it("keeps pending checks distinct from mergeability", async () => {
      const { emitted } = await run(mode, () => ({}), [context(1)], [pendingCheck()]);
      expect(emitted).toContainEqual(expect.objectContaining({ kind: "WAITING", reason: { kind: "pending-checks", pending: [pendingCheck()] } }));
    });
  });
}

for (const mode of ["single", "stack"] as const) {
  it(`${mode} progresses from unknown to ready using fresh facts`, async () => {
    const { emitted, terminal } = await run(mode, (_pr, tick) => tick === 0 ? unknown : {});
    expect(emitted.some((event) => event.kind === "WAITING")).toBe(true);
    expect(terminal).toMatchObject({ kind: "READY", exitCode: 0 });
  });

  it(`${mode} retains the intentional owner-approval stop`, async () => {
    const { terminal } = await run(mode, () => ({ mergeStateStatus: "BLOCKED", reviewDecision: "REVIEW_REQUIRED" }));
    expect(terminal).toMatchObject({ kind: "READY", exitCode: 0 });
  });
}

it("queued frontier waits for known facts before announcing a merge-queue wait", async () => {
  const { emitted, terminal } = await run("queued-stack", (_pr, tick) => tick === 0 ? unknown : tick === 1 ? {} : { state: "MERGED", mergedAt: "2026-11-02T00:00:00Z" });
  const waits = emitted.filter((event) => event.kind === "WAITING");
  expect(waits.map((event) => event.reason.kind)).toEqual(["mergeability-unknown", "merge-queue"]);
  expect(renderPretty(waits[0])).toContain("mergeability is unknown");
  expect(renderPretty(waits[0])).not.toContain("blocker-free");
  expect(terminal).toMatchObject({ kind: "COMPLETE", exitCode: 0 });
});

it("attributes an upstack unknown wait to that PR in stack mode", async () => {
  const { emitted, terminal } = await run("stack", (pr) => pr.number === 2 ? unknown : {}, [context(1), context(2)]);
  expect(emitted).toContainEqual(expect.objectContaining({ kind: "WAITING", frontier: context(2), reason: { kind: "mergeability-unknown" } }));
  expect(terminal).toMatchObject({ kind: "TIMEOUT", reason: { kind: "mergeability-unknown", frontier: context(2) } });
});

it("queued mode keeps the known merge frontier separate from upstack unknown facts", async () => {
  const { emitted } = await run("queued-stack", (pr) => pr.number === 2 ? unknown : {}, [context(1), context(2)]);
  expect(emitted).toContainEqual(expect.objectContaining({ kind: "WAITING", frontier: context(1), reason: { kind: "merge-queue", unmergedCount: 2 } }));
});

it("a higher-priority upstack blocker wins over the frontier's unknown wait", async () => {
  const first = await readSnapshot({ reader: fakeReader({ facts: unknown }), context: context(1), pendingHistory: "include", allowDraft: false });
  const second = await readSnapshot({ reader: fakeReader({ facts: { mergeable: "CONFLICTING" } }), context: context(2), pendingHistory: "include", allowDraft: false });
  expect(selectTierMajorStackDecision([first, second])).toMatchObject({ kind: "blocker", blocker: { kind: "merge-conflicts", pr: context(2) } });
});

it("status tables display unknown and behind facts without a clear-merge checkmark", async () => {
  for (const [facts, expected] of [[unknown, "unknown"], [{ mergeStateStatus: "BEHIND" }, "behind"]] as const) {
    const row = await readSnapshot({ reader: fakeReader({ facts }), context: context(1), pendingHistory: "include", allowDraft: false });
    const line = renderStatusTable([row]).split("\n")[2];
    expect(line).toContain(expected);
    expect(line.endsWith("| ✅ |")).toBe(false);
  }
});
