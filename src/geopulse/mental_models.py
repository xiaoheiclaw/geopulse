"""Load and inject mental models into LLM prompts."""
from __future__ import annotations

import re
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


def load_models(models_dir: Path | None = None) -> dict[str, dict]:
    """Load all mental model markdown files from the models directory.

    Returns a dict keyed by filename stem, each value containing:
    - title: the H1 heading from the file
    - domains: list of domains this model applies to (from ## 领域)
    - prompt_template: content under "## Prompt 注入模板"
    - full_content: the entire file content
    """
    directory = models_dir or MODELS_DIR
    models: dict[str, dict] = {}
    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        domains_match = re.search(
            r"## 领域\s*\n(.+?)(?=\n## |\Z)", content, re.DOTALL
        )
        domains = []
        if domains_match:
            raw = domains_match.group(1).strip()
            domains = [d.strip() for d in raw.split(",") if d.strip()]
        prompt_match = re.search(
            r"## Prompt 注入模板\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        prompt_template = prompt_match.group(1).strip() if prompt_match else ""
        models[path.stem] = {
            "title": title,
            "domains": domains,
            "prompt_template": prompt_template,
            "full_content": content,
        }
    return models


def build_prompt_injection(
    models_dir: Path | None = None,
    domains: list[str] | None = None,
) -> str:
    """Build a combined prompt injection string from mental models.

    If domains is provided, only include models matching those domains
    plus universal models (领域: 通用). If None, include all models.
    """
    models = load_models(models_dir)
    sections: list[str] = []
    for name, model in models.items():
        if domains is not None:
            model_domains = model["domains"]
            is_universal = "通用" in model_domains
            has_overlap = any(d in model_domains for d in domains)
            if not is_universal and not has_overlap:
                continue
        sections.append(f"### {model['title']}\n{model['prompt_template']}")
    return "\n\n".join(sections)
