import ast
from collections import defaultdict
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
MODULE_TEMPLATE_FILES = {
    "__init__.py.tmpl",
    "admin.py.tmpl",
    "api.py.tmpl",
    "apps.py.tmpl",
    "audit.py.tmpl",
    "feature_flags.py.tmpl",
    "models.py.tmpl",
    "permissions.py.tmpl",
    "services.py.tmpl",
    "tests.py.tmpl",
    "urls.py.tmpl",
    "migrations/0001_initial.py.tmpl",
    "migrations/__init__.py.tmpl",
}


def imported_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.ImportFrom):
        return [node.module or ""]
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    return []


def domain_dependencies() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {domain: set() for domain in DOMAINS}
    for path in ROOT.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        domain = path.relative_to(ROOT).parts[0]
        if domain not in DOMAINS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for imported in imported_modules(node):
                parts = imported.split(".")
                if len(parts) >= 2 and parts[0] == "obe" and parts[1] in DOMAINS:
                    target = parts[1]
                    if target != domain:
                        graph[domain].add(target)
    return graph


def dependency_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    state: dict[str, int] = defaultdict(int)
    stack: list[str] = []

    def visit(domain: str) -> None:
        state[domain] = 1
        stack.append(domain)
        for target in sorted(graph[domain]):
            if state[target] == 0:
                visit(target)
            elif state[target] == 1:
                start = stack.index(target)
                cycle = stack[start:] + [target]
                if cycle not in cycles:
                    cycles.append(cycle)
        stack.pop()
        state[domain] = 2

    for domain in sorted(graph):
        if state[domain] == 0:
            visit(domain)
    return cycles


def violations() -> list[str]:
    errors = []
    for path in ROOT.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        domain = path.relative_to(ROOT).parts[0]
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            for imported in imported_modules(node):
                if imported.startswith("obe."):
                    target = imported.split(".")[1]
                    imports_models_symbol = (
                        isinstance(node, ast.ImportFrom)
                        and imported == f"obe.{target}"
                        and any(alias.name == "models" for alias in node.names)
                    )
                    direct_model_access = ".models" in imported or imports_models_symbol
                    if (
                        domain in DOMAINS
                        and target in DOMAINS
                        and target != domain
                        and direct_model_access
                    ):
                        errors.append(f"{path}: direct cross-domain model import {imported}")
                root_import = imported.split(".")[0]
                if domain != "ai" and root_import in {"litellm", "ollama", "openai"}:
                    errors.append(f"{path}: direct AI client import outside AI gateway")
        if domain != "ai" and "localhost:11434" in source.lower():
            errors.append(f"{path}: direct model endpoint outside AI gateway")
    for cycle in dependency_cycles(domain_dependencies()):
        errors.append(f"circular domain dependency: {' -> '.join(cycle)}")
    return errors


def test_domain_boundaries():
    assert violations() == []


def test_every_domain_is_independently_parseable_and_configured():
    for domain in DOMAINS:
        package = ROOT / domain
        assert (package / "__init__.py").exists()
        assert (package / "apps.py").exists()
        for path in package.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_new_domain_template_is_complete():
    template = ROOT.parent / "docs" / "module-template"
    present = {str(path.relative_to(template)) for path in template.rglob("*.tmpl")}
    assert MODULE_TEMPLATE_FILES <= present


if __name__ == "__main__":
    found = violations()
    if found:
        raise SystemExit("\n".join(found))
    print("Architecture checks passed")
