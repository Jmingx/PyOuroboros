"""Static plugin discovery and lifecycle."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pyouroboros.core.hooks import HookBus, HookHandler, HookPhase
from pyouroboros.tools.base import Tool
from pyouroboros.tools.manager import ToolManager


@dataclass(frozen=True, slots=True)
class PluginManifest:
    name: str
    version: str
    api_version: int
    description: str
    root: Path
    entrypoint: str = "__init__.py"

    @property
    def entrypoint_path(self) -> Path:
        path = (self.root / self.entrypoint).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"plugin entrypoint escapes root: {self.entrypoint}")
        return path

    @classmethod
    def from_file(cls, path: Path) -> "PluginManifest":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"invalid plugin manifest: {path}")
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError(f"plugin manifest missing name: {path}")
        return cls(
            name=name,
            version=str(data.get("version", "0.0.0")),
            api_version=int(data.get("api_version", 1)),
            description=str(data.get("description", "")),
            root=path.parent,
            entrypoint=str(data.get("entrypoint", "__init__.py")),
        )


class HookRegistrar:
    def __init__(self, hooks: HookBus, plugin_name: str) -> None:
        self.hooks = hooks
        self.plugin_name = plugin_name

    def register(
        self,
        phase: HookPhase,
        handler: HookHandler,
        *,
        name: str | None = None,
        priority: int = 100,
    ) -> Callable[[], None]:
        return self.hooks.register(
            phase,
            handler,
            name=f"{self.plugin_name}:{name or 'hook'}",
            priority=priority,
        )


class ToolRegistrar:
    def __init__(self, tools: ToolManager) -> None:
        self.tools = tools

    def register(self, tool: Tool) -> None:
        self.tools.register(tool)


@dataclass(slots=True)
class PluginContext:
    name: str
    hooks: HookRegistrar
    tools: ToolRegistrar
    config: dict[str, Any]


@dataclass(slots=True)
class PluginSession:
    manager: "PluginManager"
    contexts: tuple[PluginContext, ...]


class PluginManager:
    """Discovers manifests, imports entrypoints, then registers per Session."""

    def __init__(self, roots: tuple[Path, ...]) -> None:
        self.roots = roots
        self.manifests: dict[str, PluginManifest] = {}
        self._modules: dict[str, Any] = {}
        self._activated = False

    def discover(self) -> tuple[PluginManifest, ...]:
        found: dict[str, PluginManifest] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for manifest_path in sorted(root.glob("*/plugin.yaml")):
                manifest = PluginManifest.from_file(manifest_path)
                if manifest.name in found:
                    raise ValueError(f"duplicate plugin: {manifest.name}")
                found[manifest.name] = manifest
        self.manifests = found
        return tuple(found.values())

    def load(self) -> None:
        if not self.manifests:
            self.discover()
        for manifest in self.manifests.values():
            module_name = f"pyouroboros_plugin_{manifest.name}"
            spec = importlib.util.spec_from_file_location(
                module_name,
                manifest.entrypoint_path,
                submodule_search_locations=[str(manifest.root)],
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load plugin {manifest.name}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            if not callable(getattr(module, "register", None)):
                raise TypeError(f"plugin {manifest.name} has no register(ctx)")
            self._modules[manifest.name] = module

    def activate(
        self,
        hooks: HookBus,
        tools: ToolManager,
        config: dict[str, Any] | None = None,
    ) -> PluginSession:
        if self._activated:
            raise RuntimeError("PluginManager is single-session; create a new manager per Session")
        if not self._modules:
            self.load()
        contexts: list[PluginContext] = []
        for manifest in self.manifests.values():
            context = PluginContext(
                name=manifest.name,
                hooks=HookRegistrar(hooks, manifest.name),
                tools=ToolRegistrar(tools),
                config=dict(config or {}),
            )
            self._modules[manifest.name].register(context)
            contexts.append(context)
        self._activated = True
        return PluginSession(manager=self, contexts=tuple(contexts))


def default_plugin_roots() -> tuple[Path, ...]:
    package_root = Path(__file__).resolve().parent
    project_root = Path.cwd() / "plugins"
    return (package_root / "builtin", project_root)


__all__ = [
    "HookRegistrar",
    "PluginContext",
    "PluginManager",
    "PluginManifest",
    "PluginSession",
    "ToolRegistrar",
    "default_plugin_roots",
]
