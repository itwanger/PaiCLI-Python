from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    path: Path
    content: str
    source: str = "project"
    version: str = ""
    tags: list[str] = field(default_factory=list)
    enabled: bool = True

    @property
    def body(self) -> str:
        return _strip_frontmatter(self.content).strip()


class SkillContextBuffer:
    def __init__(self, limit: int = 3):
        self.limit = limit
        self._items: OrderedDict[str, str] = OrderedDict()

    def push(self, name: str | None, body: str | None) -> None:
        if not name or not body:
            return
        if name in self._items:
            del self._items[name]
        self._items[name] = body
        while len(self._items) > self.limit:
            self._items.popitem(last=False)

    def drain(self) -> str:
        if not self._items:
            return ""
        chunks = [
            f"## Loaded Skill: {name}\n{body.strip()}"
            for name, body in self._items.items()
            if body.strip()
        ]
        self._items.clear()
        return "\n\n".join(chunks)

    def clear(self) -> None:
        self._items.clear()

    def is_empty(self) -> bool:
        return not self._items

    def size(self) -> int:
        return len(self._items)


class SkillStateStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or Path.home() / ".paicli" / "skills.json").expanduser()

    def disabled(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        values = data.get("disabled") if isinstance(data, dict) else None
        if not isinstance(values, list):
            return set()
        return {str(item) for item in values if str(item).strip()}

    def disable(self, name: str) -> None:
        values = self.disabled()
        values.add(name)
        self._write(values)

    def enable(self, name: str) -> None:
        values = self.disabled()
        values.discard(name)
        self._write(values)

    def _write(self, disabled: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"disabled": sorted(disabled)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class SkillRegistry:
    """Load SKILL.md files from built-in, user, and project locations."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        builtin_root: str | Path | None = None,
        user_root: str | Path | None = None,
        state_store: SkillStateStore | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        package_root = Path(__file__).resolve().parents[1]
        self.builtin_root = Path(builtin_root or package_root / "builtin_skills")
        self.user_root = Path(user_root or Path.home() / ".paicli" / "skills")
        self.project_skill_root = self.project_root / ".paicli" / "skills"
        self.state_store = state_store or SkillStateStore()
        self._skills: dict[str, Skill] | None = None

    def reload(self) -> None:
        self._skills = None

    def list(self) -> list[Skill]:
        return self.enabled_skills()

    def all_skills(self) -> list[Skill]:
        skills = self._load_all()
        return [skills[name] for name in sorted(skills)]

    def enabled_skills(self) -> list[Skill]:
        return [skill for skill in self.all_skills() if skill.enabled]

    def load(self, name: str, *, include_disabled: bool = False) -> Skill | None:
        skill = self._load_all().get(name)
        if not skill:
            return None
        if not include_disabled and not skill.enabled:
            return None
        return skill

    def enable(self, name: str) -> bool:
        if not self.load(name, include_disabled=True):
            return False
        self.state_store.enable(name)
        self.reload()
        return True

    def disable(self, name: str) -> bool:
        if not self.load(name, include_disabled=True):
            return False
        self.state_store.disable(name)
        self.reload()
        return True

    def index_text(self, max_chars: int = 4000, max_skills: int = 20) -> str:
        skills = self.enabled_skills()[:max_skills]
        if not skills:
            return ""
        lines = [
            "Available skills:",
            "Load a skill with load_skill(name) when its description matches the task.",
        ]
        for skill in skills:
            description = " ".join(skill.description.split())
            if len(description) > 500:
                description = description[:497] + "..."
            lines.append(f"- {skill.name}: {description}")
        text = "\n".join(lines)
        return text[:max_chars]

    def _load_all(self) -> dict[str, Skill]:
        if self._skills is not None:
            return self._skills
        disabled = self.state_store.disabled()
        skills: dict[str, Skill] = {}
        for source, root in [
            ("builtin", self.builtin_root),
            ("user", self.user_root),
            ("project", self.project_skill_root),
        ]:
            if not root.exists():
                continue
            for skill_file in sorted(root.glob("*/SKILL.md")):
                skill = self._load_skill_file(skill_file, source, disabled)
                if skill:
                    skills[skill.name] = skill
        self._skills = skills
        return skills

    def _load_skill_file(self, path: Path, source: str, disabled: set[str]) -> Skill | None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None
        metadata = _parse_frontmatter(content)
        name = metadata.get("name") or path.parent.name
        description = metadata.get("description") or ""
        tags = _parse_tags(metadata.get("tags", ""))
        return Skill(
            name=name,
            description=description,
            version=metadata.get("version") or "",
            tags=tags,
            source=source,
            path=path,
            content=content,
            enabled=name not in disabled,
        )


def _parse_frontmatter(content: str) -> dict[str, str]:
    if not content.startswith("---"):
        return {}
    match = re.match(r"^---\s*\n(.*?)\n---\s*", content, re.S)
    if not match:
        return {}
    lines = match.group(1).splitlines()
    metadata: dict[str, str] = {}
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        if ":" not in raw_line:
            index += 1
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "|":
            index += 1
            block: list[str] = []
            while index < len(lines) and (lines[index].startswith(" ") or not lines[index].strip()):
                block.append(lines[index].strip())
                index += 1
            metadata[key] = " ".join(part for part in block if part)
            continue
        metadata[key] = value.strip().strip('"').strip("'")
        index += 1
    return metadata


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    return re.sub(r"^---\s*\n.*?\n---\s*", "", content, count=1, flags=re.S)


def _parse_tags(raw: str) -> list[str]:
    value = raw.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [item.strip().strip('"').strip("'") for item in value.split(",") if item.strip()]
