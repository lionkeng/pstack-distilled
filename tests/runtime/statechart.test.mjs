import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { check, PINNED_FLAGS } from "../../skills/statechart/scripts/run.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const scripts = path.join(root, "skills/statechart/scripts");
const corpus = path.join(scripts, "test/corpus");
const config = "INIT Init\nNEXT Next\nINVARIANT Safe\n";
const model = (name, extra = "", imports = "") => `---- MODULE ${name} ----\n${imports}\nVARIABLE x\n${extra}\nInit == x = 0\nNext == UNCHANGED x\nSafe == x = 0\n====\n`;

function fixture(t, files) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pstack-statechart-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  for (const [name, content] of Object.entries(files)) fs.writeFileSync(path.join(dir, name), content);
  return dir;
}

function plain(dir, name) {
  assert.ok(process.env.JAVA, "JAVA must name a real Java executable for the live statechart gate");
  assert.ok(process.env.TLA2TOOLS, "TLA2TOOLS must name the pinned TLC jar for the live statechart gate");
  const r = spawnSync(process.env.JAVA, ["-cp", process.env.TLA2TOOLS, "tlc2.TLC", ...PINNED_FLAGS,
    "-metadir", path.join(dir, "plain-meta"), "-config", path.join(dir, `${name}.cfg`), name],
  { cwd: dir, encoding: "utf8", timeout: 30000 });
  assert.equal(r.error, undefined);
  return r;
}

const names = ["ChartBound", "ChartRun", "ChartTLC", "ChartNaturals", "ChartBudget", "ChartBroken", "ChartMark"];
const collisions = [
  ["Ordinary", {}],
  ["ChartBound", {}],
  ["ChartRun", {}],
  ["Operators", { extra: names.flatMap(n => [`${n} == TRUE`, `${n}1 == TRUE`]).join("\n") }],
  ["Imported", { imports: "EXTENDS ChartBound, ChartRun", files: {
    "ChartBound.tla": "---- MODULE ChartBound ----\nChartTLC == TRUE\n====\n",
    "ChartRun.tla": "---- MODULE ChartRun ----\nChartBudget == TRUE\n====\n",
  } }],
  ["Instance", { extra: "ChartTLC == INSTANCE Helpers\nUsed == ChartTLC!ChartBudget", files: {
    "Helpers.tla": "---- MODULE Helpers ----\nChartBudget == TRUE\n====\n",
  } }],
  ["Nested", { extra: "---- MODULE ChartRun ----\nChartBudget == TRUE\n====\nChartNaturals == INSTANCE ChartRun\nUsed == ChartNaturals!ChartBudget" }],
  ["ConfigNames", { extra: "CONSTANT Value", config: "CONSTANT Value = ChartBudget\n" + config }],
];

for (const [name, options] of collisions) {
  test(`live namespace ${name} agrees with plain TLC and retains its state`, async t => {
    const contents = { [`${name}.tla`]: model(name, options.extra, options.imports),
      [`${name}.cfg`]: options.config ?? config, ...options.files };
    const dir = fixture(t, contents);
    const oracle = plain(dir, name);
    assert.equal(oracle.status, 0, oracle.stdout + oracle.stderr);
    const result = await check(path.join(dir, `${name}.tla`), path.join(dir, `${name}.cfg`));
    assert.equal(result.exit, 0);
    assert.equal(result.graph.states.size, 1);
    assert.equal([...result.graph.states.values()][0].vars.x, 0);
    for (const [file, text] of Object.entries(contents)) assert.equal(fs.readFileSync(path.join(dir, file), "utf8"), text);
  });
}

test("a colliding bound module retains both failing invariant verdicts", async t => {
  const name = "ChartBound";
  const dir = fixture(t, { [`${name}.tla`]: model(name, "Bad == x # 0\nBadAgain == x # 0"),
    [`${name}.cfg`]: "INIT Init\nNEXT Next\nINVARIANTS Bad BadAgain\n" });
  const oracle = plain(dir, name);
  assert.equal(oracle.status, 12, oracle.stdout + oracle.stderr);
  const result = await check(path.join(dir, `${name}.tla`), path.join(dir, `${name}.cfg`));
  assert.equal(result.exit, 1);
  assert.deepEqual(result.rules.filter(r => r.outcome === "broken").map(r => r.rule.name).sort(), ["Bad", "BadAgain"]);
});

test("a successful model with no initial states stays valid", async t => {
  const name = "Empty";
  const dir = fixture(t, { [`${name}.tla`]: model(name).replace("Init == x = 0", "Init == FALSE /\\ x = 0"), [`${name}.cfg`]: config });
  const oracle = plain(dir, name);
  assert.equal(oracle.status, 0, oracle.stdout + oracle.stderr);
  const result = await check(path.join(dir, `${name}.tla`), path.join(dir, `${name}.cfg`));
  assert.equal(result.exit, 0);
  assert.equal(result.graph.states.size, 0);
});

function replay(t, { status, empty = false, name = "Login" }) {
  const dir = fixture(t, {});
  const saved = path.join(dir, name);
  fs.cpSync(path.join(corpus, name), saved, { recursive: true });
  if (status !== undefined) fs.writeFileSync(path.join(saved, "ChartRun.exit"), `${status}\n`);
  if (empty) fs.writeFileSync(path.join(saved, "graph.dot"), "digraph {\n}\n");
  const out = path.join(dir, "out");
  const r = spawnSync(process.execPath, [path.join(scripts, "statechart.ts"), path.join(saved, `${name}.tla`), "--out", out], {
    encoding: "utf8", timeout: 30000,
    env: { ...process.env, JAVA: path.join(scripts, "test/java.ts"), TLA2TOOLS: path.join(dir, "replay.jar"), STATECHART_REPLAY: saved },
  });
  assert.equal(r.error, undefined);
  return { ...r, out };
}

for (const status of [10, 150, 151, 152, 153, 255, 99]) {
  for (const empty of [true, false]) {
    test(`drawing exit ${status} cannot publish an ${empty ? "empty" : "existing"} graph`, t => {
      const r = replay(t, { status, empty });
      assert.equal(r.status, 2, r.stderr);
      assert.equal(fs.existsSync(r.out), false);
      assert.match(r.stderr, new RegExp(`exit ${status}`));
    });
  }
}

for (const status of [11, 12, 13, 14, 75, 76, 77]) {
  test(`drawing exit ${status} retains a useful graph with a warning`, t => {
    const r = replay(t, { status });
    assert.equal(r.status, 0, r.stderr);
    const report = fs.readFileSync(path.join(r.out, "report.md"), "utf8");
    assert.match(report, new RegExp(`exit ${status}`));
    assert.match(fs.readFileSync(path.join(r.out, "chart.mmd"), "utf8"), /stateDiagram/);
  });
  test(`drawing exit ${status} with no states cannot publish success`, t => {
    const r = replay(t, { status, empty: true });
    assert.equal(r.status, 2, r.stderr);
    assert.equal(fs.existsSync(r.out), false);
  });
}

test("successful drawing cannot discard states reported by TLC", t => {
  const r = replay(t, { status: 0, empty: true });
  assert.equal(r.status, 2, r.stderr);
  assert.equal(fs.existsSync(r.out), false);
});

for (const name of ["CounterGuard", "TypeGuard"]) {
  test(`${name} keeps the existing partial chart and report`, t => {
    const r = replay(t, { name });
    assert.equal(r.status, 1, r.stderr);
    for (const file of ["chart.mmd", "report.md"]) assert.equal(fs.readFileSync(path.join(r.out, file), "utf8"), fs.readFileSync(path.join(corpus, name, file), "utf8"));
  });
}
