"""Tests for the json_analyzer module."""

import json
from unittest.mock import patch

from typer.testing import CliRunner

from par_cc_usage.json_analyzer import (
    analyze_file,
    analyze_json_structure,
    analyze_jsonl_structure,
    app,
    detect_file_format,
    display_analysis,
    truncate_value,
)


class TestTruncateValue:
    """Test the truncate_value function."""

    def test_truncate_string_within_limit(self):
        """Test truncating string within limit."""
        result = truncate_value("short", 10)
        assert result == "short"

    def test_truncate_string_exceeds_limit(self):
        """Test truncating string that exceeds limit."""
        result = truncate_value("this is a very long string", 10)
        assert result == "this is a ..."

    def test_truncate_dict(self):
        """Test truncating dictionary values."""
        data = {"key1": "short", "key2": "this is a very long string"}
        result = truncate_value(data, 10)
        assert result == {"key1": "short", "key2": "this is a ..."}

    def test_truncate_list_within_limit(self):
        """Test truncating list within limit."""
        data = ["item1", "item2", "item3"]
        result = truncate_value(data, 10)
        assert result == ["item1", "item2", "item3"]

    def test_truncate_list_exceeds_limit(self):
        """Test truncating list that exceeds limit."""
        data = ["item1", "item2", "item3", "item4", "item5", "item6"]
        result = truncate_value(data, 10)
        assert len(result) == 6  # 5 items + "..."
        assert result[-1] == "..."

    def test_truncate_nested_structures(self):
        """Test truncating nested data structures."""
        data = {
            "dict_field": {"nested": "this is a very long string"},
            "list_field": ["short", "this is a very long string"]
        }
        result = truncate_value(data, 10)
        assert result["dict_field"]["nested"] == "this is a ..."
        assert result["list_field"][1] == "this is a ..."

    def test_truncate_primitive_types(self):
        """Test truncating primitive types."""
        assert truncate_value(42, 10) == 42
        assert truncate_value(3.14, 10) == 3.14
        assert truncate_value(True, 10) is True
        assert truncate_value(None, 10) is None


class TestDetectFileFormat:
    """Test the detect_file_format function."""

    def test_detect_json_by_extension(self, tmp_path):
        """Test detecting JSON format by file extension."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')

        result = detect_file_format(json_file)
        assert result == "json"

    def test_detect_jsonl_by_extension(self, tmp_path):
        """Test detecting JSONL format by file extension."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text('{"key": "value"}\n')

        result = detect_file_format(jsonl_file)
        assert result == "jsonl"

    def test_detect_json_by_content_single_object(self, tmp_path):
        """Test detecting JSON format by content (single object)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text('{"key": "value"}')

        result = detect_file_format(test_file)
        assert result == "json"

    def test_detect_jsonl_by_content_multiple_objects(self, tmp_path):
        """Test detecting JSONL format by content (multiple objects)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text('{"key": "value1"}\n{"key": "value2"}\n')

        result = detect_file_format(test_file)
        assert result == "jsonl"

    def test_detect_json_by_content_array(self, tmp_path):
        """Test detecting JSON format by content (array)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text('[{"key": "value1"}, {"key": "value2"}]')

        result = detect_file_format(test_file)
        assert result == "json"

    def test_detect_format_invalid_json(self, tmp_path):
        """Test detecting format with invalid JSON."""
        test_file = tmp_path / "test.txt"
        test_file.write_text('invalid json content')

        result = detect_file_format(test_file)
        assert result == "jsonl"  # Default fallback

    def test_detect_format_file_read_error(self, tmp_path):
        """Test detecting format when file cannot be read."""
        test_file = tmp_path / "nonexistent.txt"

        result = detect_file_format(test_file)
        assert result == "jsonl"  # Default fallback


class TestAnalyzeJsonStructure:
    """Test the analyze_json_structure function."""

    def test_analyze_single_json_object(self, tmp_path):
        """Test analyzing a single JSON object."""
        json_file = tmp_path / "test.json"
        data = {"name": "John", "age": 30, "active": True}
        json_file.write_text(json.dumps(data))

        result = analyze_json_structure(json_file)

        assert result["format"] == "json"
        assert result["total_objects"] == 1
        assert result["errors"] == 0
        assert "name" in result["fields"]
        assert "age" in result["fields"]
        assert "active" in result["fields"]
        assert result["fields"]["name"]["type"] == ["str"]
        assert result["fields"]["age"]["type"] == ["int"]

    def test_analyze_json_array(self, tmp_path):
        """Test analyzing a JSON array."""
        json_file = tmp_path / "test.json"
        data = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]
        json_file.write_text(json.dumps(data))

        result = analyze_json_structure(json_file, max_objects=10)

        assert result["format"] == "json"
        assert result["total_objects"] == 2
        assert result["errors"] == 0
        assert "name" in result["fields"]
        assert "age" in result["fields"]
        assert result["fields"]["name"]["count"] == 2

    def test_analyze_json_array_with_limit(self, tmp_path):
        """Test analyzing a JSON array with max_objects limit."""
        json_file = tmp_path / "test.json"
        data = [{"id": i} for i in range(10)]
        json_file.write_text(json.dumps(data))

        result = analyze_json_structure(json_file, max_objects=3)

        assert result["total_objects"] == 3
        assert result["fields"]["id"]["count"] == 3

    def test_analyze_json_primitive_value(self, tmp_path):
        """Test analyzing a JSON primitive value."""
        json_file = tmp_path / "test.json"
        json_file.write_text('"simple string"')

        result = analyze_json_structure(json_file)

        assert result["format"] == "json"
        assert result["total_objects"] == 1
        assert "_root_value" in result["fields"]
        assert result["fields"]["_root_value"]["type"] == ["str"]

    def test_analyze_json_mixed_array(self, tmp_path):
        """Test analyzing a JSON array with mixed types."""
        json_file = tmp_path / "test.json"
        data = [{"name": "John"}, "string_item", 123]
        json_file.write_text(json.dumps(data))

        result = analyze_json_structure(json_file)

        assert result["total_objects"] == 1  # Only the dict object
        assert "name" in result["fields"]
        assert "_array_item" in result["fields"]

    def test_analyze_json_decode_error(self, tmp_path):
        """Test analyzing invalid JSON."""
        json_file = tmp_path / "test.json"
        json_file.write_text('invalid json')

        with patch('par_cc_usage.json_analyzer.console'):
            result = analyze_json_structure(json_file)

        assert result["format"] == "json"
        assert result["total_objects"] == 0
        assert result["errors"] == 1
        assert result["fields"] == {}

    def test_analyze_json_file_read_error(self, tmp_path):
        """Test analyzing when file cannot be read."""
        json_file = tmp_path / "nonexistent.json"

        with patch('par_cc_usage.json_analyzer.console'):
            result = analyze_json_structure(json_file)

        assert result["errors"] == 1
        assert result["total_objects"] == 0


class TestAnalyzeJsonlStructure:
    """Test the analyze_jsonl_structure function."""

    def test_analyze_simple_jsonl(self, tmp_path):
        """Test analyzing a simple JSONL file."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [
            '{"name": "John", "age": 30}',
            '{"name": "Jane", "age": 25}',
            '{"name": "Bob", "age": 35}'
        ]
        jsonl_file.write_text('\n'.join(lines))

        result = analyze_jsonl_structure(jsonl_file)

        assert result["format"] == "jsonl"
        assert result["total_objects"] == 3
        assert result["errors"] == 0
        assert "name" in result["fields"]
        assert "age" in result["fields"]
        assert result["fields"]["name"]["count"] == 3

    def test_analyze_jsonl_with_limit(self, tmp_path):
        """Test analyzing JSONL with max_lines limit."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [f'{{"id": {i}}}' for i in range(10)]
        jsonl_file.write_text('\n'.join(lines))

        result = analyze_jsonl_structure(jsonl_file, max_lines=3)

        assert result["total_objects"] == 3
        assert result["fields"]["id"]["count"] == 3

    def test_analyze_jsonl_with_empty_lines(self, tmp_path):
        """Test analyzing JSONL with empty lines."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [
            '{"name": "John"}',
            '',  # Empty line
            '{"name": "Jane"}',
            '   ',  # Whitespace only
            '{"name": "Bob"}'
        ]
        jsonl_file.write_text('\n'.join(lines))

        result = analyze_jsonl_structure(jsonl_file)

        assert result["total_objects"] == 3
        assert result["fields"]["name"]["count"] == 3

    def test_analyze_jsonl_with_invalid_lines(self, tmp_path):
        """Test analyzing JSONL with invalid JSON lines."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [
            '{"name": "John"}',
            'invalid json',
            '{"name": "Jane"}',
            'another invalid line'
        ]
        jsonl_file.write_text('\n'.join(lines))

        with patch('par_cc_usage.json_analyzer.console'):
            result = analyze_jsonl_structure(jsonl_file)

        assert result["total_objects"] == 2
        assert result["errors"] == 2
        assert result["fields"]["name"]["count"] == 2

    def test_analyze_jsonl_varying_fields(self, tmp_path):
        """Test analyzing JSONL with varying field structures."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [
            '{"name": "John", "age": 30}',
            '{"name": "Jane", "city": "NYC"}',
            '{"name": "Bob", "age": 25, "city": "LA"}'
        ]
        jsonl_file.write_text('\n'.join(lines))

        result = analyze_jsonl_structure(jsonl_file)

        assert result["total_objects"] == 3
        assert result["fields"]["name"]["count"] == 3
        assert result["fields"]["age"]["count"] == 2
        assert result["fields"]["city"]["count"] == 2


class TestAnalyzeFile:
    """Test the analyze_file function."""

    def test_analyze_file_auto_detect_json(self, tmp_path):
        """Test analyzing file with auto-detection (JSON)."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "John", "age": 30}')

        result = analyze_file(json_file)

        assert result["format"] == "json"
        assert result["total_objects"] == 1

    def test_analyze_file_auto_detect_jsonl(self, tmp_path):
        """Test analyzing file with auto-detection (JSONL)."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text('{"name": "John"}\n{"name": "Jane"}\n')

        result = analyze_file(jsonl_file)

        assert result["format"] == "jsonl"
        assert result["total_objects"] == 2


class TestDisplayAnalysis:
    """Test the display_analysis function."""

    def test_display_json_analysis(self):
        """Test displaying JSON analysis results."""
        analysis = {
            "file_path": "/path/to/test.json",
            "format": "json",
            "total_objects": 2,
            "errors": 0,
            "fields": {
                "name": {"type": ["str"], "count": 2, "samples": ["John", "Jane"]},
                "age": {"type": ["int"], "count": 1, "samples": [30]}
            }
        }

        with patch('par_cc_usage.json_analyzer.console') as mock_console:
            display_analysis(analysis)

            # Verify console.print was called
            assert mock_console.print.called

            # Check that the panel was created with correct title
            calls = mock_console.print.call_args_list
            panel_call = calls[0][0][0]  # First call, first argument
            # The panel contains the title in its renderable content
            assert hasattr(panel_call, 'renderable')
            assert "JSON Analysis" in str(panel_call.renderable)

    def test_display_jsonl_analysis(self):
        """Test displaying JSONL analysis results."""
        analysis = {
            "file_path": "/path/to/test.jsonl",
            "format": "jsonl",
            "total_objects": 5,
            "errors": 1,
            "fields": {
                "id": {"type": ["int"], "count": 5, "samples": [1, 2, 3]}
            }
        }

        with patch('par_cc_usage.json_analyzer.console') as mock_console:
            display_analysis(analysis)

            assert mock_console.print.called

    def test_display_analysis_no_fields(self):
        """Test displaying analysis with no fields."""
        analysis = {
            "file_path": "/path/to/test.json",
            "format": "json",
            "total_objects": 0,
            "errors": 0,
            "fields": {}
        }

        with patch('par_cc_usage.json_analyzer.console') as mock_console:
            display_analysis(analysis)

            assert mock_console.print.called


class TestCliCommands:
    """Test the CLI commands."""

    def test_analyze_command_json_file(self, tmp_path):
        """Test analyze command with JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "John", "age": 30}')

        runner = CliRunner()
        result = runner.invoke(app, [str(json_file)])

        # Debug: print the result if it fails
        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            print(f"Exception: {result.exception}")

        assert result.exit_code == 0
        assert "JSON Analysis" in result.output

    def test_analyze_command_jsonl_file(self, tmp_path):
        """Test analyze command with JSONL file."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text('{"name": "John"}\n{"name": "Jane"}\n')

        runner = CliRunner()
        result = runner.invoke(app, [str(jsonl_file)])

        assert result.exit_code == 0
        assert "JSONL Analysis" in result.output

    def test_analyze_command_with_options(self, tmp_path):
        """Test analyze command with various options."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [f'{{"id": {i}, "text": "sample text {i}"}}' for i in range(5)]
        jsonl_file.write_text('\n'.join(lines))

        runner = CliRunner()
        result = runner.invoke(app, [
            str(jsonl_file),
            "--max-items", "3",
            "--max-length", "10"
        ])

        assert result.exit_code == 0

    def test_analyze_command_json_output(self, tmp_path):
        """Test analyze command with JSON output."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "John", "age": 30}')

        runner = CliRunner()
        result = runner.invoke(app, [str(json_file), "--json"])

        assert result.exit_code == 0
        # Should be valid JSON
        output_data = json.loads(result.output)
        assert "format" in output_data
        assert "fields" in output_data

    def test_analyze_command_force_format(self, tmp_path):
        """Test analyze command with forced format."""
        test_file = tmp_path / "test.txt"
        test_file.write_text('{"name": "John"}\n{"name": "Jane"}\n')

        runner = CliRunner()
        result = runner.invoke(app, [
            str(test_file),
            "--format", "jsonl"
        ])

        assert result.exit_code == 0
        assert "JSONL Analysis" in result.output

    def test_analyze_command_invalid_format(self, tmp_path):
        """Test analyze command with invalid format."""
        test_file = tmp_path / "test.txt"
        test_file.write_text('{"name": "John"}')

        runner = CliRunner()
        result = runner.invoke(app, [
            str(test_file),
            "--format", "invalid"
        ])

        assert result.exit_code == 1
        assert "Invalid format" in result.output

    def test_analyze_command_file_not_found(self):
        """Test analyze command with non-existent file."""
        runner = CliRunner()
        result = runner.invoke(app, ["/nonexistent/file.json"])

        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_analyze_command_exception_handling(self, tmp_path):
        """Test analyze command exception handling."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"name": "John"}')

        runner = CliRunner()

        with patch('par_cc_usage.json_analyzer.analyze_file', side_effect=Exception("Test error")):
            result = runner.invoke(app, [str(test_file)])

            assert result.exit_code == 1
            assert "Error analyzing file" in result.output


class TestFieldAnalysis:
    """Test field analysis functionality."""

    def test_field_type_tracking(self, tmp_path):
        """Test that field types are tracked correctly."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [
            '{"field": "string_value"}',
            '{"field": 123}',
            '{"field": true}',
            '{"field": null}'
        ]
        jsonl_file.write_text('\n'.join(lines))

        result = analyze_jsonl_structure(jsonl_file)

        field_types = set(result["fields"]["field"]["type"])
        assert "str" in field_types
        assert "int" in field_types
        assert "bool" in field_types
        assert "NoneType" in field_types

    def test_sample_collection(self, tmp_path):
        """Test that samples are collected correctly."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [
            '{"name": "John"}',
            '{"name": "Jane"}',
            '{"name": "Bob"}',
            '{"name": "Alice"}'  # Should not be in samples (max 3)
        ]
        jsonl_file.write_text('\n'.join(lines))

        result = analyze_jsonl_structure(jsonl_file)

        assert len(result["fields"]["name"]["samples"]) == 3
        assert "John" in result["fields"]["name"]["samples"]
        assert "Jane" in result["fields"]["name"]["samples"]
        assert "Bob" in result["fields"]["name"]["samples"]

    def test_complex_field_analysis(self, tmp_path):
        """Test analysis of complex field types."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [
            '{"nested": {"key": "value"}, "list": [1, 2, 3]}',
            '{"nested": {"other": "data"}, "list": ["a", "b"]}'
        ]
        jsonl_file.write_text('\n'.join(lines))

        result = analyze_jsonl_structure(jsonl_file)

        assert "dict" in result["fields"]["nested"]["type"]
        assert "list" in result["fields"]["list"]["type"]
        assert len(result["fields"]["nested"]["samples"]) == 2
        assert len(result["fields"]["list"]["samples"]) == 2


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_file(self, tmp_path):
        """Test analyzing empty file."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")

        with patch('par_cc_usage.json_analyzer.console'):
            result = analyze_json_structure(empty_file)

        assert result["total_objects"] == 0
        assert result["errors"] == 1

    def test_file_with_only_whitespace(self, tmp_path):
        """Test analyzing file with only whitespace."""
        whitespace_file = tmp_path / "whitespace.jsonl"
        whitespace_file.write_text("   \n\n  \t  \n")

        result = analyze_jsonl_structure(whitespace_file)

        assert result["total_objects"] == 0
        assert result["errors"] == 0

    def test_very_long_strings(self, tmp_path):
        """Test handling of very long strings."""
        long_string = "x" * 1000
        json_file = tmp_path / "long.json"
        json_file.write_text(f'{{"text": "{long_string}"}}')

        result = analyze_json_structure(json_file, max_string_length=50)

        sample = result["fields"]["text"]["samples"][0]
        assert len(sample) <= 53  # 50 + "..."
        assert sample.endswith("...")

    def test_deep_nesting(self, tmp_path):
        """Test handling of deeply nested structures."""
        nested_data = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        json_file = tmp_path / "nested.json"
        json_file.write_text(json.dumps(nested_data))

        result = analyze_json_structure(json_file)

        assert "level1" in result["fields"]
        assert "dict" in result["fields"]["level1"]["type"]
