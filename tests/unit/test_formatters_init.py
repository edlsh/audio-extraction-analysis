"""Test suite for src.formatters package initialization."""

import pytest


class TestFormattersPackage:
    """Test src.formatters package module structure and exports."""

    def test_module_import(self):
        """Test that src.formatters module can be imported successfully."""
        import src.formatters

        assert src.formatters is not None

    def test_module_docstring(self):
        """Test that src.formatters module has proper docstring."""
        import src.formatters

        assert src.formatters.__doc__ is not None
        assert isinstance(src.formatters.__doc__, str)
        assert len(src.formatters.__doc__.strip()) > 0

    def test_docstring_content(self):
        """Test that docstring describes the module purpose."""
        import src.formatters

        docstring_lower = src.formatters.__doc__.lower()

        # Verify the docstring mentions formatting or markdown
        expected_keywords = ["format", "export", "transcript", "markdown"]
        assert any(
            keyword in docstring_lower for keyword in expected_keywords
        ), f"Docstring should describe formatting functionality: {src.formatters.__doc__}"

    def test_all_attribute_exists(self):
        """Test that __all__ attribute is defined."""
        import src.formatters

        assert hasattr(src.formatters, "__all__")
        assert isinstance(src.formatters.__all__, list)

    def test_all_attribute_content(self):
        """Test that __all__ contains expected exports."""
        import src.formatters

        expected_exports = [
            "MarkdownFormatter",
            "MarkdownFormattingError",
            "TemplateNotFoundError",
        ]

        assert set(src.formatters.__all__) == set(
            expected_exports
        ), f"__all__ should contain {expected_exports}, got {src.formatters.__all__}"

    def test_markdown_formatter_exported(self):
        """Test that MarkdownFormatter is properly exported."""
        import src.formatters

        assert hasattr(src.formatters, "MarkdownFormatter")

        # Verify it's the correct class
        from src.formatters.markdown_formatter import MarkdownFormatter

        assert src.formatters.MarkdownFormatter is MarkdownFormatter

    def test_markdown_formatting_error_exported(self):
        """Test that MarkdownFormattingError is properly exported."""
        import src.formatters

        assert hasattr(src.formatters, "MarkdownFormattingError")

        # Verify it's the correct exception class
        from src.formatters.markdown_formatter import MarkdownFormattingError

        assert src.formatters.MarkdownFormattingError is MarkdownFormattingError

    def test_template_not_found_error_exported(self):
        """Test that TemplateNotFoundError is properly exported."""
        import src.formatters

        assert hasattr(src.formatters, "TemplateNotFoundError")

        # Verify it's the correct exception class
        from src.formatters.markdown_formatter import TemplateNotFoundError

        assert src.formatters.TemplateNotFoundError is TemplateNotFoundError

    def test_direct_import_markdown_formatter(self):
        """Test that MarkdownFormatter can be imported directly from src.formatters."""
        from src.formatters import MarkdownFormatter

        assert MarkdownFormatter is not None
        assert hasattr(MarkdownFormatter, "__name__")
        assert MarkdownFormatter.__name__ == "MarkdownFormatter"

    def test_direct_import_markdown_formatting_error(self):
        """Test that MarkdownFormattingError can be imported directly from src.formatters."""
        from src.formatters import MarkdownFormattingError

        assert MarkdownFormattingError is not None
        assert hasattr(MarkdownFormattingError, "__name__")
        assert MarkdownFormattingError.__name__ == "MarkdownFormattingError"

    def test_direct_import_template_not_found_error(self):
        """Test that TemplateNotFoundError can be imported directly from src.formatters."""
        from src.formatters import TemplateNotFoundError

        assert TemplateNotFoundError is not None
        assert hasattr(TemplateNotFoundError, "__name__")
        assert TemplateNotFoundError.__name__ == "TemplateNotFoundError"

    def test_wildcard_import(self):
        """Test that wildcard import works correctly."""
        # Import with wildcard should only import items in __all__
        namespace = {}
        exec("from src.formatters import *", namespace)

        # Check that only expected items are imported (plus builtins)
        imported_names = [name for name in namespace.keys() if not name.startswith("__")]
        expected_names = [
            "MarkdownFormatter",
            "MarkdownFormattingError",
            "TemplateNotFoundError",
        ]

        assert set(imported_names) == set(
            expected_names
        ), f"Wildcard import should only import {expected_names}, got {imported_names}"

    def test_no_unexpected_public_exports(self):
        """Test that module doesn't expose unexpected public attributes."""
        import src.formatters

        # Get all public attributes (not starting with _)
        public_attrs = [attr for attr in dir(src.formatters) if not attr.startswith("_")]

        # Should have the documented exports plus the submodules
        expected_attrs = [
            "MarkdownFormatter",
            "MarkdownFormattingError",
            "TemplateNotFoundError",
            "markdown_formatter",
            "templates",
        ]
        assert set(public_attrs) == set(
            expected_attrs
        ), f"Module should export {expected_attrs}, got {public_attrs}"

    def test_markdown_formatter_is_class(self):
        """Test that MarkdownFormatter is actually a class."""
        from src.formatters import MarkdownFormatter

        assert isinstance(MarkdownFormatter, type), "MarkdownFormatter should be a class"

    def test_markdown_formatting_error_is_exception(self):
        """Test that MarkdownFormattingError is actually an exception class."""
        from src.formatters import MarkdownFormattingError

        assert isinstance(
            MarkdownFormattingError, type
        ), "MarkdownFormattingError should be a class"
        assert issubclass(
            MarkdownFormattingError, Exception
        ), "MarkdownFormattingError should be an Exception subclass"

    def test_template_not_found_error_is_exception(self):
        """Test that TemplateNotFoundError is actually an exception class."""
        from src.formatters import TemplateNotFoundError

        assert isinstance(TemplateNotFoundError, type), "TemplateNotFoundError should be a class"
        assert issubclass(
            TemplateNotFoundError, Exception
        ), "TemplateNotFoundError should be an Exception subclass"

    def test_exception_inheritance_chain(self):
        """Test that formatter exceptions have proper exception inheritance."""
        from src.formatters import MarkdownFormattingError, TemplateNotFoundError

        # Both should inherit from Exception
        assert issubclass(MarkdownFormattingError, Exception)
        assert issubclass(MarkdownFormattingError, BaseException)
        assert issubclass(TemplateNotFoundError, Exception)
        assert issubclass(TemplateNotFoundError, BaseException)

        # Create instances and verify they're catchable
        try:
            raise MarkdownFormattingError("test error")
        except Exception as e:
            assert isinstance(e, MarkdownFormattingError)
            assert isinstance(e, Exception)

        try:
            raise TemplateNotFoundError("template.md")
        except Exception as e:
            assert isinstance(e, TemplateNotFoundError)
            assert isinstance(e, Exception)

    def test_import_does_not_raise(self):
        """Test that importing the module does not raise any exceptions."""
        try:
            pass
        except Exception as e:
            pytest.fail(f"Importing src.formatters should not raise exceptions: {e}")

    def test_import_idempotency(self):
        """Test that multiple imports don't cause issues."""
        # Import multiple times
        import src.formatters
        import src.formatters as formatters_alias
        from src.formatters import MarkdownFormatter
        from src.formatters import MarkdownFormatter as MF

        # All should reference the same objects
        assert src.formatters.MarkdownFormatter is MarkdownFormatter
        assert formatters_alias.MarkdownFormatter is MarkdownFormatter
        assert MF is MarkdownFormatter

    def test_module_name_and_package(self):
        """Test module-level attributes are correctly set."""
        import src.formatters

        assert src.formatters.__name__ == "src.formatters"
        assert src.formatters.__package__ == "src.formatters"
        assert hasattr(src.formatters, "__file__")

    def test_submodule_still_accessible(self):
        """Test that markdown_formatter submodule remains accessible after imports."""
        import src.formatters

        # The markdown_formatter submodule should still be accessible
        assert hasattr(src.formatters, "markdown_formatter")
        from src.formatters import markdown_formatter

        assert markdown_formatter is not None
        assert hasattr(markdown_formatter, "MarkdownFormatter")
        assert hasattr(markdown_formatter, "MarkdownFormattingError")
        assert hasattr(markdown_formatter, "TemplateNotFoundError")

    def test_docstring_preservation(self):
        """Test that re-exported items preserve their original docstrings."""
        from src.formatters import (
            MarkdownFormatter,
            MarkdownFormattingError,
            TemplateNotFoundError,
        )

        # Test that exported items have docstrings
        assert MarkdownFormatter.__doc__ is not None
        assert len(MarkdownFormatter.__doc__.strip()) > 0

        assert MarkdownFormattingError.__doc__ is not None
        assert len(MarkdownFormattingError.__doc__.strip()) > 0

        assert TemplateNotFoundError.__doc__ is not None
        assert len(TemplateNotFoundError.__doc__.strip()) > 0

    def test_exception_instantiation(self):
        """Test that formatter exceptions can be instantiated correctly."""
        from src.formatters import MarkdownFormattingError, TemplateNotFoundError

        # Test MarkdownFormattingError instantiation
        formatting_error = MarkdownFormattingError("Test formatting error")
        assert formatting_error is not None
        assert "Test formatting error" in str(formatting_error)

        # Test TemplateNotFoundError instantiation
        template_error = TemplateNotFoundError("missing_template.md")
        assert template_error is not None
        assert "missing_template.md" in str(template_error)

    def test_all_exports_are_defined(self):
        """Test that all items in __all__ are actually defined in the module."""
        import src.formatters

        for export_name in src.formatters.__all__:
            assert hasattr(
                src.formatters, export_name
            ), f"Export '{export_name}' in __all__ should be defined in module"

    def test_exports_match_source_module(self):
        """Test that exported items match their source module counterparts."""
        import src.formatters
        from src.formatters import markdown_formatter

        # Verify each export matches the source
        assert src.formatters.MarkdownFormatter is markdown_formatter.MarkdownFormatter
        assert src.formatters.MarkdownFormattingError is markdown_formatter.MarkdownFormattingError
        assert src.formatters.TemplateNotFoundError is markdown_formatter.TemplateNotFoundError
