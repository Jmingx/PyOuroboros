"""Tool approval policy: modes, ordered rules, and explicit decisions."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pyouroboros.core.hooks import ToolCallRequest


def _path_matches(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/")
    paths = {normalized, normalized.rsplit("/", 1)[-1]}
    patterns = {pattern}
    if pattern.startswith("**/"):
        patterns.add(pattern[3:])
    return any(
        fnmatch.fnmatch(candidate, candidate_pattern)
        for candidate in paths
        for candidate_pattern in patterns
    )


class PolicyMode(StrEnum):
    BYPASS = "bypass"
    AUTO = "auto"
    ASK = "ask"
    READONLY = "readonly"


class PolicyAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    id: str
    action: PolicyAction
    priority: int = 100
    tool: str | None = None
    side_effect: Literal["read", "write", "external", "destructive"] | None = None
    path_glob: str | None = None
    path_not_glob: str | None = None
    command_prefix: str | None = None
    host: str | None = None
    reason: str = ""
    scope: str | None = None

    def matches(self, request: ToolCallRequest) -> bool:
        tool = request.tool
        arguments = request.call.arguments

        if self.tool is not None and self.tool != tool.name:
            return False
        if self.side_effect is not None and self.side_effect != tool.side_effect:
            return False
        if self.host is not None and self.host != str(arguments.get("host", "")):
            return False

        path = arguments.get("path", arguments.get("file_path"))
        if self.path_glob is not None:
            if not isinstance(path, str) or not _path_matches(path, self.path_glob):
                return False
        if self.path_not_glob is not None:
            if isinstance(path, str) and _path_matches(path, self.path_not_glob):
                return False
        if self.command_prefix is not None:
            command = arguments.get("command")
            if not isinstance(command, str) or not command.startswith(self.command_prefix):
                return False
        return True


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    action: PolicyAction
    reason: str
    rule_id: str | None = None
    scope: str | None = None


@dataclass
class PolicyEngine:
    mode: PolicyMode = PolicyMode.AUTO
    rules: tuple[PolicyRule, ...] = field(default_factory=tuple)

    def decide(self, request: ToolCallRequest) -> PolicyDecision:
        matched = [rule for rule in self.rules if rule.matches(request)]
        for action in (PolicyAction.DENY, PolicyAction.ASK, PolicyAction.ALLOW):
            candidates = [rule for rule in matched if rule.action is action]
            if candidates:
                rule = max(candidates, key=lambda item: item.priority)
                return PolicyDecision(
                    action=action,
                    reason=rule.reason or f"matched policy rule {rule.id}",
                    rule_id=rule.id,
                    scope=rule.scope,
                )
        return self._mode_decision(request)

    def _mode_decision(self, request: ToolCallRequest) -> PolicyDecision:
        tool = request.tool
        if self.mode is PolicyMode.BYPASS:
            return PolicyDecision(PolicyAction.ALLOW, "bypass mode")
        if self.mode is PolicyMode.READONLY:
            if tool.side_effect == "read":
                return PolicyDecision(PolicyAction.ALLOW, "read-only mode permits reads")
            return PolicyDecision(PolicyAction.DENY, "read-only mode denies side effects")
        if self.mode is PolicyMode.ASK:
            if tool.side_effect == "read":
                return PolicyDecision(PolicyAction.ALLOW, "read-only tool")
            return PolicyDecision(PolicyAction.ASK, "ask mode requires approval")
        # AUTO
        if tool.requires_approval:
            return PolicyDecision(PolicyAction.ASK, "tool declares approval required")
        if tool.side_effect == "read":
            return PolicyDecision(PolicyAction.ALLOW, "read tool")
        if tool.side_effect == "destructive":
            return PolicyDecision(PolicyAction.DENY, "destructive tool is denied by default")
        return PolicyDecision(PolicyAction.ASK, f"{tool.side_effect} tool requires approval")
