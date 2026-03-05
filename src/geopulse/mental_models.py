"""Load and inject mental models into LLM prompts."""
from __future__ import annotations

import re
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


def load_models(models_dir: Path | None = None) -> dict[str, dict[str, str]]:
    """Load all mental model markdown files from the models directory.

    Returns a dict keyed by filename stem, each value containing:
    - title: the H1 heading from the file
    - prompt_template: content under "## Prompt 注入模板"
    - full_content: the entire file content
    """
    directory = models_dir or MODELS_DIR
    models: dict[str, dict[str, str]] = {}
    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        prompt_match = re.search(
            r"## Prompt 注入模板\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        prompt_template = prompt_match.group(1).strip() if prompt_match else ""
        models[path.stem] = {
            "title": title,
            "prompt_template": prompt_template,
            "full_content": content,
        }
    return models


def build_prompt_injection(models_dir: Path | None = None) -> str:
    """Build a combined prompt injection string from all mental models."""
    models = load_models(models_dir)
    sections: list[str] = []
    for name, model in models.items():
        sections.append(f"### {model['title']}\n{model['prompt_template']}")
    return "\n\n".join(sections)
