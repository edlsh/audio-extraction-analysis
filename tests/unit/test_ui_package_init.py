"""Tests for src/ui/__init__.py package initialization."""

import importlib


class TestUIPackageInit:
    """Test ui package initialization and public API exposure."""

    def test_module_can_be_imported(self):
        """Test that src.ui module can be imported without errors."""
        import src.ui

        assert src.ui is not None

    def test_console_manager_exposed_at_package_level(self):
        """Test that ConsoleManager is accessible from package level."""
        from src.ui import ConsoleManager

        assert ConsoleManager is not None

    def test_console_manager_is_correct_class(self):
        """Test that exposed ConsoleManager is the correct class."""
        from src.ui import ConsoleManager
        from src.ui.console import ConsoleManager as DirectConsoleManager

        assert ConsoleManager is DirectConsoleManager

    def test_all_attribute_exists(self):
        """Test that __all__ is defined in the module."""
        import src.ui

        assert hasattr(src.ui, "__all__")

    def test_all_contains_console_manager(self):
        """Test that __all__ includes ConsoleManager."""
        import src.ui

        assert "ConsoleManager" in src.ui.__all__

    def test_all_only_exports_intended_items(self):
        """Test that __all__ only contains intended exports."""
        import src.ui

        expected_exports = {"ConsoleManager"}
        actual_exports = set(src.ui.__all__)
        assert actual_exports == expected_exports

    def test_module_docstring_exists(self):
        """Test that module has a docstring."""
        import src.ui

        assert src.ui.__doc__ is not None
        assert len(src.ui.__doc__.strip()) > 0

    def test_module_docstring_content(self):
        """Test that module docstring describes UI components."""
        import src.ui

        assert "UI components" in src.ui.__doc__
        assert "console" in src.ui.__doc__.lower()

    def test_no_unwanted_imports_in_namespace(self):
        """Test that internal imports are not exposed at package level."""
        import src.ui

        # These should NOT be in the package namespace
        unwanted_attrs = ["sys", "threading", "json", "logging"]
        for attr in unwanted_attrs:
            assert not hasattr(src.ui, attr), f"Unexpected attribute '{attr}' found in namespace"

    def test_console_manager_instantiation_from_package(self):
        """Test that ConsoleManager can be instantiated from package import."""
        from src.ui import ConsoleManager

        console = ConsoleManager()
        assert console is not None
        assert hasattr(console, "print_stage")
        assert hasattr(console, "progress_context")

    def test_package_reload_safety(self):
        """Test that package can be safely reloaded."""
        import src.ui

        # Get initial ConsoleManager

        # Reload module
        importlib.reload(src.ui)

        # Should still be accessible
        assert hasattr(src.ui, "ConsoleManager")
        # Class should be re-imported (may or may not be same object depending on Python version)
        assert src.ui.ConsoleManager is not None

    def test_star_import_behavior(self):
        """Test that 'from src.ui import *' only imports __all__ items."""
        # Create a clean namespace
        namespace = {}
        exec("from src.ui import *", namespace)

        # Should have ConsoleManager
        assert "ConsoleManager" in namespace

        # Should not have internal implementation details
        assert "console" not in namespace  # module name
        assert "sys" not in namespace
        assert "threading" not in namespace

    def test_package_name_attribute(self):
        """Test that package __name__ is correct."""
        import src.ui

        assert src.ui.__name__ == "src.ui"

    def test_console_manager_from_package_is_functional(self):
        """Test that ConsoleManager imported from package is fully functional."""
        from src.ui import ConsoleManager

        # Create instance with JSON output mode
        console = ConsoleManager(json_output=True)
        assert console.json_output is True

        # Verify it has expected methods
        assert callable(getattr(console, "print_stage", None))
        assert callable(getattr(console, "progress_context", None))
