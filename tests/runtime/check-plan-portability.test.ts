import { afterEach, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const checker = resolve(import.meta.dir, "../../skills/poteto-mode/scripts/check-plan.mjs");
const template = resolve(import.meta.dir, "../../skills/poteto-mode/playbooks/multi-phase-plan.md");
const roots: string[] = [];
afterEach(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true }); });
const rule = "Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.";
const roles = ["execution", "swarm", "verification", "opening-a-pr"];

function fixture() {
	const root = mkdtempSync(join(tmpdir(), "plan portability "));
	roots.push(root);
	const product = join(root, "product");
	const installed = join(root, "installed skills");
	mkdirSync(product); mkdirSync(installed);
	const git = (...args: string[]) => execFileSync("git", ["-C", product, ...args], { encoding: "utf8", env: { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: "/dev/null" } }).trim();
	git("init", "--quiet", "--template=", "-b", "develop");
	git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "--quiet", "-m", "fixture");
	const context = {
		product: { root: product, trunkRef: "develop", trunkSha: git("rev-parse", "HEAD") },
		skillSources: roles.map(role => {
			const path = join(installed, `${role}.md`);
			const text = `# ${role}\n`;
			writeFileSync(path, text);
			return { role, path, sha256: createHash("sha256").update(text).digest("hex") };
		}),
		audit: { mode: "poll", intervalSeconds: 10, maxWaitSeconds: 120, progressPath: join(root, "progress.tsv"), stopCondition: "All planned checks pass", recurringHandle: undefined as string | undefined },
	};
	return { root, product, installed, context };
}

function plan(context: unknown) {
	return `# Demo

## How to read this
One box is one unit of work and names the evidence. Check a box only when its evidence exists. See playbooks/.
${rule}

## Program checklist
### Arm the program
\`\`\`pstack-plan-context
${JSON.stringify(context, null, 2)}
\`\`\`
### Spawn owners
### PR mechanics
### Verdict and merge
### Boot recipe
Post a status message when the state changes.

## PR 1
**Depends on.** None.
**Files.**
- [ ] Edit the command.
**Build.**
- [ ] Correct the result.
**You see.**
- [ ] The command returns the result.
**Verify, unit.** ${rule}
- [ ] Run the test.
**Verify, live.** ${rule} Ten lanes on \`auto\` at the PR head
${Array.from({length:10}, (_,i) => `- [ ] Lane ${i+1}. Save \`lane-${i+1}.png\`. Pass when the result matches.`).join("\n")}
**Verify, perf.** ${rule}
- [ ] Metric. Time.
- [ ] Probe. Run it.
- [ ] Baseline. Record it.
- [ ] Rule. No regression.
**Review gate.** None.
**Merge.**
- [ ] Hand off for review.

## Close the program
Complete the checks.

## Appendix A. Prototype evidence
Record the result.
`;
}
function run(root: string, body: string, startup = false) {
	const file = join(root, "plan.md");
	writeFileSync(file, body);
	return spawnSync("node", [checker, file, ...(startup ? ["--startup"] : [])], { encoding: "utf8" });
}
function succeeds(result: ReturnType<typeof run>) { expect(result.stderr).toBe(""); expect(result.status).toBe(0); }
function fails(result: ReturnType<typeof run>, diagnostic: string) { expect(result.status).toBe(1); expect(result.stderr).toContain(diagnostic); }

test("external installed sources and a develop trunk support bounded polling", () => {
	const f = fixture(); succeeds(run(f.root, plan(f.context)));
});
test("recurring plans validate before arming and require a receipt at startup", () => {
	const f = fixture(); f.context.audit.mode = "recurring";
	succeeds(run(f.root, plan(f.context)));
	writeFileSync(f.context.audit.progressPath, "ready\n");
	fails(run(f.root, plan(f.context), true), "recurringHandle");
	f.context.audit.recurringHandle = "host-task-123";
	succeeds(run(f.root, plan(f.context), true));
});
test("polling startup requires durable progress state", () => {
	const f = fixture(); fails(run(f.root, plan(f.context), true), "progressPath");
	writeFileSync(f.context.audit.progressPath, "ready\n"); succeeds(run(f.root, plan(f.context), true));
});
test("changed source content and missing source files fail", () => {
	const f = fixture(); writeFileSync(f.context.skillSources[0]!.path, "changed\n");
	fails(run(f.root, plan(f.context)), "sha256");
	rmSync(f.context.skillSources[0]!.path); fails(run(f.root, plan(f.context)), "readable file");
});
test("source directories cannot stand in for instruction files", () => {
	const f = fixture(); f.context.skillSources[0]!.path = f.installed;
	fails(run(f.root, plan(f.context)), "readable file");
});
test("each mandatory source role and identity is required", () => {
	for (const role of roles) {
		const f = fixture(); f.context.skillSources = f.context.skillSources.filter(s => s.role !== role);
		fails(run(f.root, plan(f.context)), role);
	}
	const f = fixture(); f.context.skillSources[0]!.sha256 = ""; fails(run(f.root, plan(f.context)), "sha256");
});
test("source roles and context blocks cannot be duplicated", () => {
	const f = fixture(); f.context.skillSources.push(f.context.skillSources[0]!);
	fails(run(f.root, plan(f.context)), "duplicate");
	const g = fixture(); fails(run(g.root, plan(g.context) + `\n\`\`\`pstack-plan-context\n${JSON.stringify(g.context)}\n\`\`\`\n`), "exactly one");
});
test("product ref must resolve to the recorded commit", () => {
	const f = fixture(); f.context.product.trunkSha = "0".repeat(40);
	fails(run(f.root, plan(f.context)), "trunkSha");
	f.context.product.trunkRef = "missing"; fails(run(f.root, plan(f.context)), "trunkRef");
});
test("invalid cadence fields fail without an arbitrary shell command", () => {
	for (const [key, value] of [["mode", "cron"], ["intervalSeconds", 0], ["maxWaitSeconds", -1], ["progressPath", ""], ["stopCondition", ""]] as const) {
		const f = fixture(); Object.assign(f.context.audit, { [key]: value });
		fails(run(f.root, plan(f.context)), key);
	}
});
test("context must be real JSON outside other code examples", () => {
	const f = fixture(); fails(run(f.root, plan(f.context).replace(JSON.stringify(f.context, null, 2), "not json")), "JSON");
	const nested = plan(f.context).replace("```pstack-plan-context", "````markdown\n```pstack-plan-context").replace("\n```\n### Spawn", "\n```\n````\n### Spawn");
	fails(run(f.root, nested), "exactly one");
});
test("the converted template accepts filled context in both cadence modes", () => {
	const f = fixture();
	const source = readFileSync(template, "utf8");
	const skeleton = source.split("````markdown\n")[1]?.split("\n````")[0];
	expect(skeleton).toBeDefined();
	expect(skeleton).toContain("```pstack-plan-context");
	for (const mode of ["poll", "recurring"]) {
		f.context.audit.mode = mode;
		let body = skeleton!.replace(/```pstack-plan-context\n[\s\S]*?\n```/, `\`\`\`pstack-plan-context\n${JSON.stringify(f.context, null, 2)}\n\`\`\``);
		body = body.replace(/<[^>\n]+>/g, "fixture").replace(/Ten lanes on `fixture`/, "Ten lanes on `auto`");
		succeeds(run(f.root, body));
	}
});
