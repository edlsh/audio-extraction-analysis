#!/usr/bin/env python3
"""Analyze module dependencies and generate dependency graph.

This script:
- Extracts imports from all Python modules
- Builds a directed dependency graph
- Detects circular dependencies
- Generates architecture baseline
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import networkx as nx


def analyze_module_imports(module_path: Path) -> set[str]:
    """Extract all imports from a Python module.

    Args:
        module_path: Path to Python module

    Returns:
        Set of module names imported
    """
    try:
        with module_path.open() as f:
            tree = ast.parse(f.read(), filename=str(module_path))
    except SyntaxError:
        print(f"Warning: Syntax error in {module_path}", file=sys.stderr)
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

    return imports


def build_dependency_graph(src_dir: Path) -> nx.DiGraph:
    """Build directed graph of module dependencies.

    Args:
        src_dir: Path to source directory

    Returns:
        NetworkX directed graph of dependencies
    """
    graph = nx.DiGraph()

    for module_file in src_dir.rglob("*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in module_file.parts or "test" in module_file.name:
            continue

        # Get module name relative to src
        try:
            module_name = str(module_file.relative_to(src_dir.parent))
            module_name = module_name.replace("/", ".").replace(".py", "")
        except ValueError:
            continue

        imports = analyze_module_imports(module_file)

        for imp in imports:
            # Only track internal src imports
            if imp.startswith("src"):
                graph.add_edge(module_name, imp)

    return graph


def detect_cycles(graph: nx.DiGraph) -> list[list[str]]:
    """Detect circular dependencies in graph.

    Args:
        graph: Dependency graph

    Returns:
        List of cycles (each cycle is a list of modules)
    """
    try:
        cycles = list(nx.simple_cycles(graph))
        return cycles
    except Exception:
        return []


def generate_architecture_snapshot(src_dir: Path) -> dict:
    """Capture current architecture state.

    Args:
        src_dir: Path to source directory

    Returns:
        Dictionary with architecture metrics
    """
    graph = build_dependency_graph(src_dir)
    cycles = detect_cycles(graph)

    return {
        "total_modules": graph.number_of_nodes(),
        "total_dependencies": graph.number_of_edges(),
        "circular_dependencies": len(cycles),
        "cycles": [[str(node) for node in cycle] for cycle in cycles] if cycles else [],
        "is_dag": nx.is_directed_acyclic_graph(graph),
        "max_depth": (
            nx.dag_longest_path_length(graph) if nx.is_directed_acyclic_graph(graph) else None
        ),
    }


def main():
    """Main entry point."""
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / "src"

    if not src_dir.exists():
        print(f"Error: Source directory not found: {src_dir}", file=sys.stderr)
        sys.exit(1)

    # Generate architecture snapshot
    snapshot = generate_architecture_snapshot(src_dir)

    # Print to stdout
    print(json.dumps(snapshot, indent=2))

    # Save baseline
    baseline_file = project_root / ".architecture_baseline.json"
    with baseline_file.open("w") as f:
        json.dump(snapshot, f, indent=2)

    print(f"\nArchitecture baseline saved to {baseline_file}", file=sys.stderr)

    # Report issues
    if snapshot["circular_dependencies"] > 0:
        print(
            f"\n⚠️  Warning: {snapshot['circular_dependencies']} circular dependencies detected:",
            file=sys.stderr,
        )
        for cycle in snapshot["cycles"]:
            print(f"  - {' -> '.join(cycle)}", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n✅ No circular dependencies detected", file=sys.stderr)


if __name__ == "__main__":
    main()
