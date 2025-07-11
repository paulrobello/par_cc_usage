"""JSON and JSONL file analyzer with field truncation for large files."""

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer()
console = Console()

JSON_VALUE = str | int | float | bool | None | dict[str, Any] | list[Any]


def truncate_value(value: JSON_VALUE, max_length: int = 100) -> JSON_VALUE:
    """Truncate string values to specified length.

    Args:
        value: JSON value to truncate
        max_length: Maximum string length before truncation

    Returns:
        Truncated value
    """
    if isinstance(value, str):
        if len(value) > max_length:
            return value[:max_length] + "..."
        return value
    elif isinstance(value, dict):
        return {k: truncate_value(v, max_length) for k, v in value.items()}
    elif isinstance(value, list):
        if len(value) > 5:  # Limit list display to 5 items
            truncated_list: list[Any] = [truncate_value(v, max_length) for v in value[:5]]
            truncated_list.append("...")
            return truncated_list
        return [truncate_value(v, max_length) for v in value]
    else:
        return value


def detect_file_format(file_path: Path) -> str:
    """Detect if file is JSON or JSONL format.

    Args:
        file_path: Path to the file

    Returns:
        'json' or 'jsonl' based on format detection
    """
    # First check file extension
    if file_path.suffix == ".json":
        return "json"
    elif file_path.suffix == ".jsonl":
        return "jsonl"

    # If extension is ambiguous, try to detect format
    try:
        with open(file_path, encoding="utf-8") as f:
            first_line = f.readline().strip()

            # Try to parse as complete JSON
            try:
                json.loads(first_line)
                # Check if there's a second line
                second_line = f.readline().strip()
                if second_line and second_line.startswith("{"):
                    return "jsonl"  # Multiple JSON objects = JSONL
                else:
                    return "json"  # Single JSON object = JSON
            except json.JSONDecodeError:
                # Try to read entire file as JSON
                f.seek(0)
                try:
                    json.load(f)
                    return "json"
                except json.JSONDecodeError:
                    return "jsonl"  # Assume JSONL if JSON parsing fails
    except Exception:
        # Default to JSONL if detection fails
        return "jsonl"


def analyze_json_structure(file_path: Path, max_objects: int = 10, max_string_length: int = 100) -> dict[str, Any]:
    """Analyze JSON file structure.

    Args:
        file_path: Path to JSON file
        max_objects: Maximum number of objects to analyze (for arrays)
        max_string_length: Maximum string length before truncation

    Returns:
        Analysis results dictionary
    """
    field_info: dict[str, dict[str, Any]] = {}
    object_count = 0
    error_count = 0

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            # Single JSON object
            object_count = 1
            _analyze_object(data, field_info, max_string_length)
        elif isinstance(data, list):
            # Array of JSON objects
            for i, item in enumerate(data):
                if max_objects > 0 and i >= max_objects:
                    break
                if isinstance(item, dict):
                    object_count += 1
                    _analyze_object(item, field_info, max_string_length)
                else:
                    # Handle non-object items in array
                    field_info["_array_item"] = {
                        "type": [type(item).__name__],
                        "samples": [truncate_value(item, max_string_length)],
                        "count": 1,
                    }
        else:
            # Single primitive value
            field_info["_root_value"] = {
                "type": [type(data).__name__],
                "samples": [truncate_value(data, max_string_length)],
                "count": 1,
            }
            object_count = 1

    except json.JSONDecodeError as e:
        error_count += 1
        console.print(f"[red]JSON decode error: {e}[/red]")
    except Exception as e:
        error_count += 1
        console.print(f"[red]Error reading file: {e}[/red]")

    # Convert sets to lists for JSON serialization
    for field in field_info.values():
        if isinstance(field["type"], set):
            field["type"] = list(field["type"])

    return {
        "file_path": str(file_path),
        "format": "json",
        "total_objects": object_count,
        "errors": error_count,
        "fields": field_info,
    }


def analyze_jsonl_structure(file_path: Path, max_lines: int = 10, max_string_length: int = 100) -> dict[str, Any]:
    """Analyze JSONL file structure by streaming through lines.

    Args:
        file_path: Path to JSONL file
        max_lines: Maximum lines to analyze (0 for all)
        max_string_length: Maximum string length before truncation

    Returns:
        Analysis results dictionary
    """
    field_info: dict[str, dict[str, Any]] = {}
    line_count = 0
    error_count = 0

    with open(file_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if line_num > max_lines and max_lines > 0:
                break

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                line_count += 1
                _analyze_object(data, field_info, max_string_length)

            except json.JSONDecodeError as e:
                error_count += 1
                if error_count <= 3:  # Show first 3 errors
                    console.print(f"[red]Error on line {line_num}: {e}[/red]")

    # Convert sets to lists for JSON serialization
    for field in field_info.values():
        if isinstance(field["type"], set):
            field["type"] = list(field["type"])

    return {
        "file_path": str(file_path),
        "format": "jsonl",
        "total_objects": line_count,
        "errors": error_count,
        "fields": field_info,
    }


def _analyze_object(data: dict[str, Any], field_info: dict[str, dict[str, Any]], max_string_length: int) -> None:
    """Analyze a single JSON object and update field information.

    Args:
        data: JSON object to analyze
        field_info: Dictionary to update with field information
        max_string_length: Maximum string length before truncation
    """
    for key, value in data.items():
        if key not in field_info:
            field_info[key] = {"type": set(), "samples": [], "count": 0}

        field_info[key]["type"].add(type(value).__name__)
        field_info[key]["count"] += 1

        # Store truncated samples
        if len(field_info[key]["samples"]) < 3:
            field_info[key]["samples"].append(truncate_value(value, max_string_length))


def analyze_file(file_path: Path, max_items: int = 10, max_string_length: int = 100) -> dict[str, Any]:
    """Analyze JSON or JSONL file structure.

    Args:
        file_path: Path to file to analyze
        max_items: Maximum items to analyze (lines for JSONL, objects for JSON arrays)
        max_string_length: Maximum string length before truncation

    Returns:
        Analysis results dictionary
    """
    file_format = detect_file_format(file_path)

    if file_format == "json":
        return analyze_json_structure(file_path, max_items, max_string_length)
    else:
        return analyze_jsonl_structure(file_path, max_items, max_string_length)


def display_analysis(analysis: dict[str, Any]) -> None:
    """Display analysis results in a formatted way.

    Args:
        analysis: Analysis results dictionary
    """
    format_str = analysis["format"].upper()
    console.print(Panel(f"[bold]{format_str} Analysis: {analysis['file_path']}[/bold]"))
    console.print(f"Format: [blue]{format_str}[/blue]")
    console.print(f"Total objects analyzed: [green]{analysis['total_objects']}[/green]")
    if analysis["errors"] > 0:
        console.print(f"Errors encountered: [red]{analysis['errors']}[/red]")
    console.print()

    if not analysis["fields"]:
        console.print("[yellow]No fields found in the analyzed data.[/yellow]")
        return

    # Create table for field information
    table = Table(title="Field Structure", show_header=True)
    table.add_column("Field Name", style="cyan", width=30)
    table.add_column("Type(s)", style="magenta", width=20)
    table.add_column("Count", style="green", width=10)
    table.add_column("Sample Values", style="yellow", overflow="fold")

    for field_name, field_data in sorted(analysis["fields"].items()):
        types = ", ".join(field_data["type"])
        count = str(field_data["count"])

        # Format samples
        samples: list[str] = []
        for sample in field_data["samples"]:
            if isinstance(sample, dict | list):
                # Format dict/list as indented JSON for readability
                formatted = json.dumps(sample, indent=2)
                # Limit to first 200 chars for display
                if len(formatted) > 200:
                    formatted = formatted[:200] + "..."
                samples.append(formatted)
            else:
                samples.append(repr(sample))

        sample_text = "\n---\n".join(samples)
        table.add_row(field_name, types, count, sample_text)

    console.print(table)


@app.command()
def analyze(
    file_path: Path = typer.Argument(..., help="Path to JSON or JSONL file to analyze"),
    max_items: int = typer.Option(10, "--max-items", "-n", help="Maximum items to analyze (0 for all)"),
    max_string_length: int = typer.Option(100, "--max-length", "-l", help="Maximum string length before truncation"),
    show_json: bool = typer.Option(False, "--json", help="Output raw JSON instead of formatted display"),
    force_format: str = typer.Option(None, "--format", "-f", help="Force format detection (json or jsonl)"),
) -> None:
    """Analyze JSON or JSONL file structure with field truncation.

    Supports both JSON (.json) and JSONL (.jsonl) formats. Format is automatically
    detected based on file extension and content analysis.
    """
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    # Validate force_format if provided
    if force_format and force_format not in ["json", "jsonl"]:
        console.print(f"[red]Error: Invalid format '{force_format}'. Use 'json' or 'jsonl'.[/red]")
        raise typer.Exit(1)

    if not show_json:
        console.print(f"[cyan]Analyzing {file_path}...[/cyan]")

    try:
        # Override format detection if force_format is provided
        if force_format:
            if force_format == "json":
                analysis = analyze_json_structure(file_path, max_items, max_string_length)
            else:
                analysis = analyze_jsonl_structure(file_path, max_items, max_string_length)
        else:
            analysis = analyze_file(file_path, max_items, max_string_length)

        if show_json:
            # Convert the analysis to proper JSON format
            print(json.dumps(analysis, indent=2))
        else:
            display_analysis(analysis)

    except Exception as e:
        console.print(f"[red]Error analyzing file: {e}[/red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
