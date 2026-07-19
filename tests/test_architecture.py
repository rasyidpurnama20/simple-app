import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "obe"
DOMAINS = {
    "identity",
    "curriculum",
    "learning",
    "assessment",
    "evidence",
    "analytics",
    "quality",
    "ai",
    "secure_exam",
    "academic_lifecycle",
    "integration",
}


def violations() -> list[str]:
    errors = []
    for path in ROOT.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        domain = path.relative_to(ROOT).parts[0]
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            imported = ""
            if isinstance(node, ast.ImportFrom):
                imported = node.module or ""
            elif isinstance(node, ast.Import):
                imported = " ".join(alias.name for alias in node.names)
            if imported.startswith("obe."):
                target = imported.split(".")[1]
                direct_model_access = imported.endswith(".models") or imported.count(".") == 1
                if (
                    domain in DOMAINS
                    and target in DOMAINS
                    and target != domain
                    and direct_model_access
                ):
                    errors.append(f"{path}: direct cross-domain model import {imported}")
        if domain != "ai" and any(
            token in source.lower()
            for token in ("localhost:11434", "import openai", "import ollama")
        ):
            errors.append(f"{path}: direct model access outside AI gateway")
    return errors


def test_domain_boundaries():
    assert violations() == []


if __name__ == "__main__":
    found = violations()
    if found:
        raise SystemExit("\n".join(found))
    print("Architecture checks passed")
