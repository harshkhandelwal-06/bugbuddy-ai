"""Load prompt files from prompts/ (single source of truth for app, runner and PDF)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = ROOT / "prompts"

# version label -> ordered list of prompt files (a version is a workflow of 1 or 2 prompts)
VERSIONS = {
    "v1": ["v1/v1_baseline.txt"],
    "v2": ["v2/v2_json_output.txt"],
    "v3": ["v3/v3_examples_low_temp.txt"],
    "v4": ["final/P1_diagnose.txt", "final/P2_fix_explain.txt"],
}


@dataclass
class Prompt:
    path: str
    settings: dict = field(default_factory=dict)
    system: str = ""
    user: str = ""

    @property
    def id(self) -> str:
        return self.settings.get("id", self.path)

    @property
    def temperature(self) -> float | None:
        t = str(self.settings.get("temperature", "default")).strip().lower()
        return None if t in ("default", "none", "") else float(t)

    def render_user(self, **variables: str) -> str:
        out = self.user
        for k, v in variables.items():
            out = out.replace("{" + k + "}", v)
        return out


def load_prompt(rel_path: str) -> Prompt:
    text = (PROMPT_DIR / rel_path).read_text(encoding="utf-8")
    parts = re.split(r"^### (SETTINGS|SYSTEM|USER)\s*$", text, flags=re.M)
    sections = {parts[i]: parts[i + 1].strip("\n") for i in range(1, len(parts) - 1, 2)}
    settings = {}
    for line in sections.get("SETTINGS", "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            settings[k.strip()] = v.strip()
    return Prompt(path=rel_path, settings=settings,
                  system=sections.get("SYSTEM", ""), user=sections.get("USER", ""))


def load_version(version: str) -> list[Prompt]:
    return [load_prompt(p) for p in VERSIONS[version]]
