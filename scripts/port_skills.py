#!/usr/bin/env python3
"""Convert an upstream pstack checkout into portable Agent Skills."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


RUNTIME_MARKERS = re.compile(
    r"(?:\bCursor\b|\.cursor/|\bAsk(?:User)?Question\b|`?Task`? tool|"
    r"\bsubagent_type\b|\brun_in_background\b|/loop\b|"
    r"claude-fable-5-thinking-max|claude-opus-5-thinking-xhigh|"
    r"gpt-5\.6-sol-max|grok-4\.6-fast-xhigh|cursor-team-kit)"
)
VENDOR_MODEL_SLUG = re.compile(
    r"\b(?:claude|gpt|gemini|grok|llama|mistral|deepseek|qwen)"
    r"(?:-[a-z0-9][a-z0-9._-]*)+\b",
    re.IGNORECASE,
)
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
PORTABLE_EXECUTION = """## Portable execution

Use the host's native planning, user-interaction, and delegation capabilities.
When delegation or parallel execution is unavailable, perform the same
independent roles sequentially in the current context and then synthesize.
When model selection is unavailable, use the current model. Treat model-role
names as capability labels, not vendor identifiers. Access conversation
history only when the host explicitly exposes it; otherwise use the current
conversation and durable repository artifacts.
"""
POTETO_PERSISTENCE = """## Activation and persistence

Activate this mode only when the user requests it or another pstack workflow
directs you to it. Once activated, keep applying it on later turns when a
playbook matches or the task needs its rigor. Stop applying it when the user
opts out.
"""
POTETO_COMPATIBILITY = (
    "Some playbooks optionally use git, GitHub CLI, conversation history, delegation, or a "
    "branch-stacking or recurring-execution capability; without recurring execution, poll in the "
    "active session. Bundled helpers require Bun, first-run network access, and write access to "
    "their installed scripts directory for dependencies."
)

SEMANTIC_REWRITES: Sequence[Tuple[str, str]] = (
    (
        "Use the `AskQuestion` tool (structured multi-choice)",
        "Use the host's structured user-interaction capability",
    ),
    (
        "This skill orchestrates three others: an inline mining pass (see step 1), Cursor's built-in "
        "`create-skill` (authoring), and the **unslop** skill (prose discipline). It sequences them; "
        "it doesn't replace them.",
        "This skill combines an inline mining pass, an Agent Skills-compatible authoring and "
        "validation workflow, and the **unslop** skill for prose discipline.",
    ),
    (
        "Use Cursor's built-in `create-skill` skill to author the skill.",
        "Author the skill against the Agent Skills specification and validate it with the host's "
        "available conformance workflow.",
    ),
    (
        "- Frontmatter `description`: trigger on their name + `/<handle>-mode` + \"work in their "
        "style\", not on generic keywords like \"write code\" or \"review PR\".",
        "- Frontmatter `description`: trigger on their name, `<handle>-mode`, and \"work in their "
        "style\", not on generic keywords like \"write code\" or \"review PR\".",
    ),
    (
        "- Frontmatter `disable-model-invocation: true` by default. Mode skills are heavy and "
        "opinionated; they should only apply when the user explicitly invokes them (by name or slash "
        "command), not auto-trigger on description matching. Opt out only if the user explicitly "
        "wants their mode to apply on every turn.",
        "- Use only standard Agent Skills frontmatter. Encode explicit activation in the description "
        "(for example, \"Use only when the user explicitly requests this mode\") and optional "
        "namespaced metadata; do not add host-specific invocation-control fields.",
    ),
    (
        "Apply the **unslop** skill and `create-skill`'s writing guidelines to every line.",
        "Apply the **unslop** skill and the Agent Skills authoring guidelines to every line.",
    ),
    (
        "A `create-skill`-style test/iterate benchmark loop isn't useful here.",
        "A generic skill-authoring benchmark loop isn't useful here.",
    ),
    (
        "`create-skill` alone, no mining required.",
        "use the Agent Skills authoring workflow directly; no mining is required.",
    ),
    (
        "the host's built-in `create-skill` skill: skill authoring process and writing guidelines.",
        "the Agent Skills specification and the host's available authoring and validation workflow.",
    ),
    (
        "**PRs.** `/deslop` the diff before commit; `/no-comments` the diff before review; apply the "
        "**unslop** skill to the PR description and commit bodies.",
        "**PRs.** Apply an available prose-cleanup workflow to agent-authored text before commit; "
        "run the **no-comments** skill before review; apply the **unslop** skill to the PR "
        "description and commit bodies.",
    ),
    (
        "About to `AskQuestion` on",
        "Before asking the user about",
    ),
    (
        "Enumerate the model slugs you can pass to a `Task` subagent in this session",
        "Enumerate the model identifiers the host can assign to delegated workers in this session",
    ),
    (
        "Agent-facing prose also follows the **create-skill** skill (Cursor's built-in for "
        "authoring SKILL.md files).",
        "When authoring skills, follow the Agent Skills specification and the host's available "
        "skill-validation workflow.",
    ),
    (
        "Before commit → the `deslop` skill from the `cursor-team-kit` plugin (`/deslop`).",
        "Before commit → apply an available prose-cleanup workflow to agent-authored text.",
    ),
    (
        "Shipping UI / IDE / CLI → the matching control skill. `cursor-team-kit` publishes "
        "`control-cli` (CLIs and TUIs) and `control-ui` (browser / Electron / web UIs).",
        "Shipping UI / IDE / CLI → use the project's available UI or CLI verification harness.",
    ),
    (
        "Use the **create-skill** skill (Cursor's built-in for authoring SKILL.md files).",
        "Follow the Agent Skills specification and use the host's available skill-authoring and "
        "validation workflow.",
    ),
    (
        "Start broad: Glob for relevant directories, Grep for key types/interfaces/class names",
        "Start broad: enumerate relevant directories and search for key types, interfaces, and "
        "class names",
    ),
    (
        "The agent does its own exploration (Glob, Grep, Read)",
        "The worker does its own exploration (file discovery, text search, and focused reads)",
    ),
    (
        "Use Read, Grep, and Glob as needed.",
        "Use focused file reads, text search, and file discovery as needed.",
    ),
    (
        '- The user said "reflect" or "/reflect".',
        '- The user explicitly said "reflect".',
    ),
    (
        "The parent finds its own transcript file before fanning out. The system prompt names the "
        "active workspace's `agent-transcripts/` directory; use that path. Do not glob across "
        "`~/.cursor/projects/*/`. That crosses workspace boundaries and reads private chats from "
        "unrelated projects.\n\n"
        "```bash\n"
        "ls -t <agent-transcripts>/*.jsonl <agent-transcripts>/*/*.jsonl "
        "<agent-transcripts>/*/subagents/*.jsonl 2>/dev/null | head -10\n"
        "```\n\n"
        "Three transcript layouts: legacy flat (`<id>.jsonl`), current nested "
        "(`<id>/<id>.jsonl`), and subagent (`<parent>/subagents/<child>.jsonl`).\n\n"
        "For each candidate, read the first JSONL line and check that "
        "`message.content[0].text` contains the conversation's opening user prompt. Take the "
        "matching path. If no path resolves, write a tight digest of the session and pass that "
        "instead.",
        "Use only conversation history explicitly exposed by the host for the active workspace or "
        "supplied by the user. Ask the host for recent records and use exposed metadata to identify "
        "the active conversation. Do not assume a filesystem layout or JSON schema, and never probe "
        "private host storage. If no history capability resolves the active record, write a tight "
        "digest of the current conversation and pass that instead.",
    ),
    (
        "Shape: one or two questions with 4-6 options each, `allow_multiple: true` for category "
        "questions.",
        "Shape: one or two questions with 4-6 options each; allow multiple selections for category "
        "questions when the host supports it.",
    ),
    (
        "Before handing back, you must spawn a subagent on a different model family from the one "
        "that did the work. Self-review is not a substitute; the point is fresh eyes you cannot "
        "bring yourself. The subagent reads the audit trail and the run's transcript, then flags "
        "what the user should pay attention to. Not a redo of the work, a scan for what's "
        "suboptimal or risky.",
        "Before handing back, seek an independent review of the audit trail and conversation "
        "record when the host supports delegation. Prefer a reviewer on a different model family "
        "for genuinely fresh eyes. When independent review is unavailable, perform the same "
        "structured risk scan inline and disclose that it was self-review. This is not a redo of "
        "the work; it flags what the user should scrutinize.",
    ),
    (
        "Every reply for a run that produced a trail ends with an \"Attention\" section. Lead "
        "with the reviewer's model on its own line (`reviewed by <model>`), then list each flag "
        "pointing to specific rows or moments. \"No flags\" is a valid value; the model name is "
        "not. The self-audit asks if the log told the truth; this asks what the user should still "
        "scrutinize even when it did.",
        "Every reply for a run that produced a trail ends with an \"Attention\" section. When an "
        "independent review ran, lead with `reviewed by <model-or-role>`. Otherwise lead with "
        "`self-review only (independent reviewer unavailable)`. Then list each flag with specific "
        "evidence; \"No flags\" is valid. The self-audit asks if the log told the truth, while this "
        "scan asks what the user should still scrutinize.",
    ),
    (
        "More when needed: Xcode `DerivedData` and `iOS DeviceSupport`; "
        "`~/Library/Application Support/Cursor` (`state.vscdb.backup`, and "
        "`snapshots/roots/<root>` where a `<root>` named for a folder you opened as a workspace "
        "balloons); package caches (pnpm, uv, brew, yarn). Clear only caches the user has not said "
        "to keep.",
        "More when needed: platform build caches such as Xcode `DerivedData` and "
        "`iOS DeviceSupport`, plus package caches such as pnpm, uv, brew, and yarn. Treat editor "
        "and application state as user data, not cache; delete it only when the user names the "
        "exact product and path and approves after inspection.",
    ),
    (
        "Use the tools available to you (Read, Grep, Glob) to explore.",
        "Use the available file-reading, text-search, and file-discovery capabilities to explore.",
    ),
    (
        "Use Glob to find directories and files, Grep to find key symbols, Read to understand the "
        "actual implementation.",
        "Discover relevant directories and files, search for key symbols, and read the actual "
        "implementation.",
    ),
    (
        "Tool calls (Shell, Grep, MCP, etc.) that match a skill's documented commands",
        "Capability calls (shell commands, text search, connected-source lookups, and similar) "
        "that match a skill's documented operations",
    ),
    (
        "- Prefer `subagent_type: \"poteto-agent\"`. `generalPurpose` is the fallback. Never use "
        "the built-in `plan` subagent_type; it ignores this skill.",
        "- Instruct delegated implementers to read and apply poteto-mode first. If the host cannot "
        "preload a worker profile, include that requirement in the brief.",
    ),
    (
        "**Just do it.** Use any MCP tool. Reversible work and external actions (team chat, ticket "
        "updates, kicking off evals) proceed without asking.",
        "**Stay within the active authorization boundary.** Read-only discovery may proceed when "
        "the source is in scope. External messages, tracker mutations, pull-request creation, "
        "deployment, destructive operations, and other consequential writes require the user's "
        "stated scope and the active host's authorization rules.",
    ),
    (
        "**Use `subagent_type: \"poteto-agent\"` for any subagent you spawn inside a playbook step** "
        "(code-writing delegates, ad-hoc helpers). `/poteto-mode` and `poteto-agent` route through "
        "the same wrapper. Routed workflow skills (`how`, `why`, `interrogate`, `reflect`, `swarm`) "
        "set their own `subagent_type` for diverse-model review; respect what the skill prescribes, "
        "don't override to `poteto-agent`.",
        "**For a delegated worker inside a playbook, instruct it to read and apply poteto-mode first.** "
        "If the host cannot preload a named worker profile, include that requirement in the brief. "
        "Routed workflow skills (`how`, `why`, `interrogate`, `reflect`, `swarm`) define their own "
        "independent-review roles; preserve those roles.",
    ),
    (
        "agent mode (readonly strips MCP)",
        "the least privilege needed for its assigned reads or writes",
    ),
    (
        "One message, three `Task` calls, `subagent_type: generalPurpose`, explicit `model:` on each, "
        "agent mode (`readonly: false`). Reviewers need MCP access for context lookups (tickets, "
        "chat threads, observability traces referenced in the transcript); readonly strips MCPs. "
        "The prompt forbids file writes; the parent applies edits.",
        "Delegate three independent reviews together when supported. Give each a general-purpose "
        "worker role and an available model suited to its lens. Grant only the read access needed "
        "for connected-source lookups; the prompt forbids file writes and the parent applies edits.",
    ),
    (
        "One `Task` call, `subagent_type: generalPurpose`, using your configured reflect-judgment "
        "model (default `claude-fable-5-thinking-max`), agent mode (`readonly: false`). The "
        "synthesizer's quality check includes spot-verifying citations, which can require MCP "
        "access; readonly strips MCPs.",
        "Delegate one synthesis pass using the configured judgment role or current model. Grant "
        "only the read access needed to spot-verify citations.",
    ),
    (
        "`readonly`: `false` (agent mode). The synthesizer's quality check spot-verifies citations, "
        "which can require MCP access. Readonly/Ask mode strips MCPs and defeats that.",
        "Requested access: read connected sources without mutating them. Grant only the read "
        "capabilities needed to spot-verify citations.",
    ),
    (
        "Transcripts live at `~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl`, "
        'where `<slug>` is the workspace path with the leading slash dropped and each "/" turned '
        'into "-" (so `/Users/you/proj` becomes `Users-you-proj`). Every line is one chat message.',
        "Use only conversation history explicitly exposed by the host or supplied by the user. "
        "History locations and formats vary by host. If no history capability is available, "
        "reconstruct context from the current conversation, a user-supplied digest, git state, "
        "pull requests, branches, and durable task artifacts.",
    ),
    (
        "The system prompt names the workspace's `agent-transcripts/` directory. Use only that path. "
        "Don't glob across `~/.cursor/projects/*/`. That crosses workspace boundaries and reads "
        "private chats from unrelated projects.",
        "Use only a conversation-history source explicitly exposed for the active workspace. "
        "Never probe private storage or another workspace's history.",
    ),
    (
        "The system prompt names the active workspace's `agent-transcripts/` directory; use that path. "
        "Do not glob across `~/.cursor/projects/*/`. That crosses workspace boundaries and reads "
        "private chats from unrelated projects.",
        "Use only a conversation-history source explicitly exposed for the active workspace. "
        "Never probe private storage or another workspace's history.",
    ),
    (
        "the active workspace's `agent-transcripts/` directory (the system prompt names the path). "
        "Don't glob across `~/.cursor/projects/*/`; that reads unrelated private chats.",
        "the active workspace's explicitly exposed conversation history. Never probe private "
        "storage or another workspace's history.",
    ),
    (
        "Before spawning investigators, list the available MCPs from the Cursor environment. "
        "Use the available-tools map when present. Otherwise inspect the `mcps/` directory Cursor "
        "exposes for enabled MCP servers.",
        "Before delegating investigations, enumerate connected tools and knowledge sources when "
        "the host exposes discovery. Never probe undocumented host directories. Treat MCP as one "
        "possible connector protocol rather than a required runtime.",
    ),
    (
        "- `readonly`: `false` (agent mode). **Do not use readonly/Ask mode.** It strips MCP access, "
        "which disables MCP-backed investigators entirely. The source control investigator would "
        "be safe in readonly, but keep modes uniform. Investigators still shouldn't write anything. "
        "That's a posture, not a sandbox.",
        "- Requested access: read connected sources without mutating them. Use the least privilege "
        "that still permits those reads, and do not infer authorization for writes.",
    ),
    (
        "Open a todolist with one entry per phase before starting.",
        "Maintain a plan or checklist with one entry per phase before starting.",
    ),
    (
        "Open a todolist with one entry per phase before launching anything.",
        "Maintain a plan or checklist with one entry per phase before launching anything.",
    ),
    (
        "Open a todolist with one entry per phase before starting. Autonomous mode without "
        "checkpoints needs the list to show phase position and keep phases from silently disappearing.",
        "Maintain a plan or checklist with one entry per phase before starting. Autonomous mode "
        "without checkpoints needs the list to show phase position and keep phases from silently "
        "disappearing.",
    ),
    (
        "Tell every subagent to order candidates by real modification time (`ls -t`) and never by "
        "UUID name, grep the topic first",
        "Tell every delegated worker to order candidates by real modification time exposed by the "
        "host, never by opaque identifier, and search the topic first",
    ),
)

# Run broad terminology cleanup only after path-specific rewrites. Doing it
# earlier would corrupt names such as `agent-transcripts/` before the configured
# host-path rewrite gets a chance to recognize them.
POST_SEMANTIC_REWRITES: Sequence[Tuple[str, str]] = (
    ("chat UUID", "conversation identifier"),
    ("chat findings by UUID", "conversation findings by their available identifier"),
    ("transcript path or digest", "conversation-record path or digest"),
    ("full transcript", "full conversation record"),
    ("transcripts", "conversation records"),
    ("transcript", "conversation record"),
    ("`Read` tool calls", "file reads"),
    ("cloud_base_branch", "remote base branch"),
)


class PortError(ValueError):
    """Raised when upstream content cannot be converted safely."""


def _split_frontmatter(text: str, source: Path) -> Tuple[List[str], str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise PortError(f"{source}: missing opening YAML frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise PortError(f"{source}: missing closing YAML frontmatter delimiter") from exc
    return lines[1:end], "\n".join(lines[end + 1 :]).lstrip("\n")


def _decode_source_scalar(raw: str, source: Path, key: str) -> str:
    raw = raw.strip()
    if not raw or raw in {"|", ">", "|-", ">-"}:
        raise PortError(f"{source}: {key} must be a one-line scalar")
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PortError(f"{source}: invalid quoted {key}: {exc}") from exc
        if not isinstance(value, str):
            raise PortError(f"{source}: {key} must be a string")
        return value
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


def _source_metadata(frontmatter: Sequence[str], source: Path) -> Tuple[str, str, bool]:
    values: Dict[str, str] = {}
    explicit = False
    for line in frontmatter:
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        if key in {"name", "description"}:
            values[key] = _decode_source_scalar(raw, source, key)
        elif key == "disable-model-invocation" and raw.strip().lower() == "true":
            explicit = True
    if "name" not in values or "description" not in values:
        raise PortError(f"{source}: source skill must define name and description")
    return values["name"], values["description"], explicit


def _load_rewrites(path: Path) -> Sequence[Tuple[str, str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortError(f"could not read rewrite configuration {path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise PortError(f"{path}: rewrite configuration must be a JSON object")
    if raw.get("schema_version") != 1 or not isinstance(raw.get("literal"), list):
        raise PortError(f"{path}: unsupported rewrite configuration")
    rewrites: List[Tuple[str, str]] = []
    for index, item in enumerate(raw["literal"]):
        if not isinstance(item, Mapping) or not isinstance(item.get("from"), str) or not isinstance(item.get("to"), str):
            raise PortError(f"{path}: literal rewrite {index} must contain string from/to values")
        rewrites.append((item["from"], item["to"]))
    return rewrites


def _rewrite_text(text: str, rewrites: Sequence[Tuple[str, str]], skill_names: Sequence[str]) -> str:
    for old, new in SEMANTIC_REWRITES:
        text = text.replace(old, new)
    for old, new in rewrites:
        text = text.replace(old, new)
    for old, new in POST_SEMANTIC_REWRITES:
        text = text.replace(old, new)

    # Remove slash-command syntax only when it is an invocation, not a file path.
    if skill_names:
        command_names = "|".join(re.escape(name) for name in sorted(skill_names, key=len, reverse=True))
        text = re.sub(rf"(?<![.\w/>])/({command_names})\b", r"\1", text)
    # These are optional Cursor companion workflows, not portable dependencies.
    # Keep their intent while avoiding an unbundled skill name or slash command.
    text = re.sub(
        r"(?:(?:Cursor's|the host's) built-in )?`?create-skill`?(?: skill)?",
        "Agent Skills authoring workflow",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"`?/?deslop`?", "prose-cleanup workflow", text)
    post_rewrites = (
        (
            "Drafts or revises a personal -mode skill via Agent Skills authoring workflow + unslop",
            "Drafts or revises a personal -mode skill with an Agent Skills-compatible authoring "
            "workflow and unslop",
        ),
        (
            "follow Agent Skills authoring workflow's YAML rules",
            "follow the Agent Skills frontmatter rules",
        ),
        (
            "the **Agent Skills authoring workflow** skill (the host's built-in for authoring "
            "SKILL.md files)",
            "an Agent Skills-compatible authoring and validation workflow",
        ),
        (
            "the prose-cleanup workflow skill from the `optional companion tooling` plugin "
            "(`prose-cleanup workflow`)",
            "an available prose-cleanup workflow",
        ),
        (
            "the prose-cleanup workflow skill from the `optional companion tooling` plugin "
            "(prose-cleanup workflow)",
            "an available prose-cleanup workflow",
        ),
        (
            "`control-ui` or `control-cli` from `optional companion tooling`",
            "the project's available UI or CLI verification harness",
        ),
        (
            "`control-cli` or `control-ui` runtime verification (from `optional companion tooling`)",
            "runtime verification with the project's available UI or CLI harness",
        ),
        (
            "`control-ui` or `control-cli` runtime verification (from `optional companion tooling`)",
            "runtime verification with the project's available UI or CLI harness",
        ),
        (
            "`control-cli` or `control-ui` from `optional companion tooling`",
            "the project's available CLI or UI verification harness",
        ),
        (
            "Browser / Electron / Web UIs: the `control-ui` skill from the `optional companion "
            "tooling` plugin.",
            "Browser / Electron / Web UIs: use the project's available UI verification harness.",
        ),
        (
            "CLIs and TUIs: the `control-cli` skill from the `optional companion tooling` plugin.",
            "CLIs and TUIs: use the project's available CLI verification harness.",
        ),
        (
            "the host's built-in **babysit** skill",
            "another host PR-monitoring workflow",
        ),
        (
            "the host's built-in babysit skill",
            "another host PR-monitoring workflow",
        ),
        (
            "Read each candidate's local conversation record under the active workspace's "
            "`<host-conversation-history>/` directory (the system prompt names this path). Do not "
            "glob across `<host-project-history-root>/`; that crosses workspace boundaries and "
            "reads private chats from unrelated projects.",
            "Use only each candidate's conversation record when the host explicitly exposes it for "
            "the active workspace. Never probe private host storage or another workspace.",
        ),
        (
            "A local conversation record under the active workspace's "
            "`<host-conversation-history>/` directory (the system prompt names the path; do not "
            "glob across `<host-project-history-root>/`, that crosses workspace boundaries and "
            "reads private chats from unrelated projects)",
            "A conversation record explicitly exposed by the host for the active workspace",
        ),
        (
            "reading local conversation records under `<host-conversation-history>/`",
            "reading conversation records explicitly exposed by the active host",
        ),
        ("delegation operation subagent", "delegated worker"),
        ("the loop skill", "the host's recurring-run capability"),
        ("parallel cloud workers", "parallel delegated workers when supported"),
        ("the cloud concurrency limit", "the host's concurrency limit"),
        ("Cloud agents cannot read the local store", "Remote workers may not access local-only state"),
        ("the cloud agent's status", "the delegated worker's status"),
        ("the cloud environment forces", "the remote execution model requires"),
        ("a cloud agent", "a remote worker"),
        ("cloud-agent status / liveness probe", "delegated-worker status or liveness probe"),
        (
            "a cloud-sleeper wake chain (a sleeping cloud agent that re-arms its own wake)",
            "the host's recurring-run capability with a re-armed wake or heartbeat",
        ),
        (
            "via the relevant control skill",
            "with the project's available verification harness",
        ),
        (
            "via the matching control skill",
            "with the project's available verification harness",
        ),
        ("via the control skill", "with the project's available verification harness"),
        ("the matching control skill", "the project's available verification harness"),
        ("the control skill", "the project's available verification harness"),
        ("No control skill", "No verification harness"),
        ('"make a control skill for this repo"', '"make a verification skill for this repo"'),
        (
            "and not another host PR-monitoring workflow, whose description matches the same words. ",
            "Use this bundled playbook for those requests. ",
        ),
        (
            "This playbook replaces another host PR-monitoring workflow for these requests, so do "
            "not route there even though its description matches the same words.",
            "Use this bundled playbook for these requests rather than a similarly triggered host "
            "workflow.",
        ),
        (
            "After opening, run another host PR-monitoring workflow",
            "After opening, follow `playbooks/babysit.md` to monitor checks and review feedback",
        ),
        (
            "another host PR-monitoring workflow after opening the PR",
            "the bundled Babysit playbook after opening the PR",
        ),
        (
            "the **Babysit** playbook (`playbooks/babysit.md`), Use this bundled playbook for those "
            "requests.",
            "the bundled **Babysit** playbook (`playbooks/babysit.md`).",
        ),
        (
            "`gh pr view <number>` before referencing PR status.",
            "On GitHub, use `gh pr view <number>` before referencing PR status when `gh` is "
            "available; otherwise use the host's source-control connector or state that status "
            "could not be verified.",
        ),
        (
            "Pull PR bodies and discussion via `gh` for any substantive commits:",
            "When the repository is on GitHub and `gh` is available, pull PR bodies and discussion "
            "for substantive commits. Otherwise use an available source-control connector and "
            "record the PR-discussion gap:",
        ),
        (
            "Source control is always available through git and `gh`.",
            "Local source history is available through git in a checkout. PR discussion is "
            "available only when `gh` or another source-control connector is configured.",
        ),
        ("Git history, `gh` for PRs", "Git history and an available PR connector"),
        (
            'Or "Not searched. This should not happen because git and `gh` are always expected."',
            'Or "Not searched. No checkout or source-control connector was available; PR discussion '
            'is an explicit evidence gap."',
        ),
        (
            "check them with `git` and `gh`.",
            "check local state with `git` and use `gh` only for GitHub when available; otherwise "
            "use the host's source-control connector and report any PR-status gap.",
        ),
        (
            "One specific prior chat to resume is the `session-pickup` playbook, not this.",
            "For one specific prior conversation, use poteto-mode's `session-pickup` playbook when "
            "it is installed. Otherwise reconstruct decisions, open work, and live state inline "
            "from the exposed record or a user-supplied digest.",
        ),
        (
            "Create `orchestrate/<project-slug>/` in the current agent's store (path in the system "
            "prompt).",
            "Set `ORCH_STORE` to a durable writable directory explicitly exposed by the host or "
            "chosen in the active workspace. If it is workspace-local, keep it uncommitted. Never "
            "guess a private host-state path. Create `<ORCH_STORE>/orchestrate/<project-slug>/`.",
        ),
        (
            "Probe read-only: the ledger, `units.tsv`, `gh`, pushed branches, the delegated worker's "
            "status in the host task dashboard.",
            "Probe read-only using the ledger, `units.tsv`, pushed branches, `gh` when available, "
            "and a worker-status capability when the host exposes one. Otherwise mark live worker "
            "status unknown rather than guessing.",
        ),
        (
            "the control-skill path",
            "the project's available verification harness",
        ),
        (
            "the full Task schema including `environment`",
            "only the delegation and execution-environment options exposed by the host",
        ),
        (
            "nesting works to depth 3, and a nested spawn has only the delegation and execution-"
            "environment options exposed by the host",
            "use nested delegation only when supported; otherwise have the coordinator spawn "
            "workers directly or run them sequentially",
        ),
        (
            "Restacks run in cloud; a local restack at this scale takes the laptop down.",
            "Run restacks remotely when that capability is available; otherwise serialize them "
            "locally and reduce concurrency to protect the machine.",
        ),
        (
            "After a host restart: local agents are dead, cloud work is not.",
            "After a host restart, local workers may be gone while remotely delegated work may "
            "still be running; verify both through capabilities the host exposes.",
        ),
        (
            "its spawn budget with the cloud default and the local exception list",
            "its spawn budget, the remote-when-supported default, and the local exception list",
        ),
        (
            "verbatim paste is for cloud spawns and every resume",
            "verbatim paste is for remote spawns when supported and every resume",
        ),
        (
            "Run a unit's verifier on a different model family from its worker.",
            "When the host offers model choice, use a different model family for the verifier; "
            "otherwise use an independent worker or apply the same verification rubric inline.",
        ),
        (
            "a dedicated verifier agent (on a different model family than the worker)",
            "a dedicated verifier agent (using a different model family when selectable, "
            "otherwise an independent worker)",
        ),
    )
    for old, new in post_rewrites:
        text = text.replace(old, new)
    text = VENDOR_MODEL_SLUG.sub("available-model", text)
    text = re.sub(r"\bTask\b", "delegation operation", text)
    text = text.replace("delegation operation subagent", "delegated worker")
    text = re.sub(r"\bcloud agents\b", "remote workers", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcloud agent\b", "remote worker", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcloud-agent\b", "remote-worker", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcloud-sleeper\b", "recurring-run worker", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcloud concurrency\b", "host concurrency", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcloud environment\b", "remote execution model", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcloud\b", "remote", text, flags=re.IGNORECASE)
    return text


def _inject_after_heading(body: str, section: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            return "\n".join(lines[: index + 1] + ["", section.rstrip(), ""] + lines[index + 1 :]).rstrip() + "\n"
    return section.rstrip() + "\n\n" + body.rstrip() + "\n"


def _render_frontmatter(
    name: str,
    description: str,
    origin: str,
    explicit: bool,
    compatibility: Optional[str] = None,
) -> str:
    lines = [
        "---",
        f"name: {json.dumps(name, ensure_ascii=False)}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        "license: MIT",
    ]
    if compatibility:
        lines.append(f"compatibility: {json.dumps(compatibility, ensure_ascii=False)}")
    lines.extend(
        [
            "metadata:",
            f"  pstack-distilled-origin: {json.dumps(origin, ensure_ascii=False)}",
        ]
    )
    if explicit:
        lines.append('  pstack-distilled-activation: "explicit"')
    lines.extend(["---", ""])
    return "\n".join(lines)


def _portable_worktree_script(text: str) -> str:
    old = """# Transcripts dir: ~/.cursor/projects/<slugified-repo-path>/agent-transcripts.
slug=$(printf '%s' "$main_wt" | sed 's#^/##; s#/#-#g')
transcripts="$HOME/.cursor/projects/$slug/agent-transcripts"
"""
    new = """# Optional conversation history. Set this only to a directory explicitly exposed
# by the active host or supplied by the user. Leaving it empty skips chat checks.
transcripts="${PSTACK_CONVERSATION_HISTORY_DIR:-}"
"""
    if old not in text:
        raise PortError("worktree-audit.sh: expected upstream transcript block was not found")
    text = text.replace(old, new)
    old_scan = """\t\tf=$(rg -l -e "${wt}/" -e "${wt}\\\"" "$transcripts" 2>/dev/null \\
\t\t\t| xargs stat -f '%m %N' 2>/dev/null | sort -rn | head -1)
\t\tif [ -n "$f" ]; then last_ts=$(echo "$f" | awk '{print $1}')
\t\t\tlast=$(date -r "$last_ts" '+%Y-%m-%d' 2>/dev/null); fi
"""
    new_scan = """\t\tf=$(rg -l -e "${wt}/" -e "${wt}\\\"" "$transcripts" 2>/dev/null \\
\t\t\t| while IFS= read -r record; do
\t\t\t\tif stat -f '%m %N' "$record" >/dev/null 2>&1; then
\t\t\t\t\tstat -f '%m %N' "$record"
\t\t\t\telse
\t\t\t\t\tprintf '%s %s\\n' "$(stat -c '%Y' "$record")" "$record"
\t\t\t\tfi
\t\t\tdone | sort -rn | head -1)
\t\tif [ -n "$f" ]; then last_ts=$(echo "$f" | awk '{print $1}')
\t\t\tlast=$(date -r "$last_ts" '+%Y-%m-%d' 2>/dev/null \\
\t\t\t\t|| date -d "@$last_ts" '+%Y-%m-%d' 2>/dev/null); fi
"""
    if old_scan not in text:
        raise PortError("worktree-audit.sh: expected upstream history scan was not found")
    return text.replace(old_scan, new_scan)


def _copy_resource(
    source: Path,
    destination: Path,
    rewrites: Sequence[Tuple[str, str]],
    skill_names: Sequence[str],
) -> None:
    if source.is_symlink():
        raise PortError(f"{source}: source symlinks are not imported")
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        destination.write_bytes(raw)
    else:
        if source.name == "worktree-audit.sh":
            text = _portable_worktree_script(text)
        if source.suffix.lower() == ".md":
            text = _rewrite_text(text, rewrites, skill_names)
        else:
            # Do not rewrite source code as prose. Only the package namespace is a
            # safe mechanical change; host-path code receives an explicit override.
            text = text.replace(
                "@cursor-skill/poteto-mode-tools", "@pstack-distilled/poteto-mode-tools"
            )
        destination.write_text(text, encoding="utf-8")
    source_mode = source.stat().st_mode
    destination.chmod(0o755 if source_mode & 0o111 else 0o644)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _remove_cross_skill_links(output_root: Path) -> None:
    """Keep cross-skill references as prose; the standard has no dependency model."""

    for markdown_path in sorted(output_root.rglob("*.md")):
        relative = markdown_path.relative_to(output_root)
        if len(relative.parts) < 2:
            continue
        skill_root = output_root / relative.parts[0]
        text = markdown_path.read_text(encoding="utf-8")

        def replace(match: re.Match[str]) -> str:
            target = match.group(2).split("#", 1)[0].strip()
            if not target or target.startswith(("https://", "http://", "mailto:", "data:")):
                return match.group(0)
            resolved = (markdown_path.parent / target).resolve()
            if _is_within(resolved, output_root.resolve()) and not _is_within(
                resolved, skill_root.resolve()
            ):
                return match.group(1)
            return match.group(0)

        rewritten = MARKDOWN_LINK.sub(replace, text)
        if rewritten != text:
            markdown_path.write_text(rewritten, encoding="utf-8")


def _port_comment_reviewer(
    pstack_root: Path,
    no_comments_root: Path,
    rewrites: Sequence[Tuple[str, str]],
    skill_names: Sequence[str],
) -> None:
    source = pstack_root / "agents" / "comment-sicko.md"
    if source.is_symlink() or source.parent.is_symlink():
        raise PortError(f"{source}: source symlinks are not imported")
    if not source.is_file():
        raise PortError(f"{source}: required upstream comment-reviewer prompt is missing")
    _, body = _split_frontmatter(source.read_text(encoding="utf-8"), source)
    body = body.replace("# Comment Sicko", "# Comment reviewer lens")
    body = body.replace("My first output when spawned is exactly this.\n\nYes... Ha ha ha... Yes!\n\n", "")
    body = _rewrite_text(body, rewrites, skill_names)
    destination = no_comments_root / "references" / "comment-reviewer.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(body.rstrip() + "\n", encoding="utf-8")


def port_skills(pstack_root: Path, output_root: Path, rewrites_path: Path) -> int:
    source_skills = pstack_root / "skills"
    if source_skills.is_symlink():
        raise PortError(f"{source_skills}: source skills directory cannot be a symlink")
    if not source_skills.is_dir():
        raise PortError(f"{source_skills}: upstream skills directory is missing")
    if output_root.exists():
        raise PortError(f"{output_root}: staging output must not already exist")
    output_root.mkdir(parents=True)

    rewrites = _load_rewrites(rewrites_path)
    source_entries = sorted(source_skills.iterdir())
    for source_entry in source_entries:
        if source_entry.is_symlink():
            raise PortError(f"{source_entry}: top-level source symlinks are not imported")
    skill_dirs = [path for path in source_entries if path.is_dir()]
    skill_names = [path.name for path in skill_dirs]
    if not skill_dirs:
        raise PortError(f"{source_skills}: no skills found")
    if len(skill_names) != len(set(skill_names)):
        raise PortError(f"{source_skills}: duplicate skill directory names")

    for source_skill in skill_dirs:
        skill_name = source_skill.name
        if source_skill.is_symlink():
            raise PortError(f"{source_skill}: source skill directories cannot be symlinks")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name) or len(skill_name) > 64:
            raise PortError(f"{source_skill}: directory name is not portable")
        skill_file = source_skill / "SKILL.md"
        if not skill_file.is_file():
            raise PortError(f"{source_skill}: missing SKILL.md")

        frontmatter, source_body = _split_frontmatter(skill_file.read_text(encoding="utf-8"), skill_file)
        _, description, explicit = _source_metadata(frontmatter, skill_file)
        had_runtime_markers = bool(RUNTIME_MARKERS.search(source_body))
        body = _rewrite_text(source_body, rewrites, skill_names)

        if skill_name == "no-comments":
            original = (
                '1. Spawn the delegation capability with `worker role: "Comment Sicko"`. '
                "Pass the scope. Do not restate its rules."
            )
            portable = (
                "1. Read [`references/comment-reviewer.md`](references/comment-reviewer.md). "
                "When delegation is available, give that lens and the scope to an independent "
                "read-only reviewer; otherwise apply the lens inline."
            )
            if original not in body:
                raise PortError(f"{skill_file}: expected no-comments delegation step was not found")
            body = body.replace(original, portable).replace("Comment Sicko", "the comment reviewer")

        if had_runtime_markers:
            body = _inject_after_heading(body, PORTABLE_EXECUTION)
        if skill_name == "poteto-mode":
            body = _inject_after_heading(body, POTETO_PERSISTENCE)

        portable_description = _rewrite_text(description, rewrites, skill_names)
        if skill_name == "no-comments":
            portable_description = portable_description.replace(
                "Spawn Comment Sicko",
                "Review comments with an independent deletion-first lens",
            )
        if explicit:
            portable_description = (
                "Use only when explicitly requested or when another pstack skill directs you to it. "
                + portable_description
            )
        if len(portable_description) > 1024:
            raise PortError(f"{skill_file}: converted description exceeds 1024 characters")

        if skill_name == "setup-pstack":
            model_labels = (
                "fast-code-model",
                "deep-code-model",
                "judgment-model",
                "independent-review-model",
            )
            for line in body.splitlines():
                if line.startswith(
                    (
                        "feature, refactoring:",
                        "bug-fix:",
                        "perf-issue:",
                        "hillclimb:",
                        "judgment and prose:",
                        "hardest tasks:",
                        "how explorer:",
                        "how explainer:",
                        "how critics:",
                        "why investigators:",
                        "why synthesizer:",
                        "reflect tooling:",
                        "reflect judgment, divergent, synthesizer:",
                        "arena runners:",
                        "arena cross-judge pool:",
                        "swarm workers:",
                        "architect runners:",
                        "interrogate reviewers:",
                    )
                ):
                    value = line.split(":", 1)[1]
                    count = sum(value.count(label) for label in model_labels)
                    replacement = ", ".join(["auto"] * max(count, 1))
                    body = body.replace(line, line.split(":", 1)[0] + ": " + replacement)

        destination_skill = output_root / skill_name
        destination_skill.mkdir()
        rendered = _render_frontmatter(
            name=skill_name,
            description=portable_description,
            origin=f"cursor/plugins/pstack/skills/{skill_name}",
            explicit=explicit,
            compatibility=POTETO_COMPATIBILITY if skill_name == "poteto-mode" else None,
        ) + body.rstrip() + "\n"
        (destination_skill / "SKILL.md").write_text(rendered, encoding="utf-8")

        for source in sorted(source_skill.rglob("*")):
            if source.is_symlink():
                raise PortError(f"{source}: source symlinks are not imported")
            if source == skill_file or source.is_dir():
                continue
            relative = source.relative_to(source_skill)
            _copy_resource(source, destination_skill / relative, rewrites, skill_names)

    no_comments = output_root / "no-comments"
    if no_comments.is_dir():
        _port_comment_reviewer(pstack_root, no_comments, rewrites, skill_names)
    _remove_cross_skill_links(output_root)
    return len(skill_dirs)


__all__ = ["PortError", "port_skills"]
