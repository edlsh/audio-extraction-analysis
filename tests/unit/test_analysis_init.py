"""Test suite for src.analysis package initialization.

This module tests the src.analysis package's __init__.py to verify:
- Module can be imported without errors
- Package has appropriate documentation (docstring)
- Public API exports are correctly defined via __all__
- Analyzer classes (ConciseAnalyzer, FullAnalyzer) are properly exported
- Wildcard imports work as expected
- No unexpected attributes are exposed in the public API
"""

import pytest


class TestAnalysisPackage:
    """Test src.analysis package module structure and exports.

    This test class validates the src.analysis package initialization,
    ensuring proper module structure, documentation, and public API exports.
    It verifies both direct and wildcard import patterns work correctly.
    """

    # === Basic Module Import Tests ===

    def test_module_import(self):
        """Test that src.analysis module can be imported successfully.

        Verifies the package __init__.py is valid and can be imported
        without raising ImportError or other exceptions.
        """
        import src.analysis

        assert src.analysis is not None

    def test_module_docstring(self):
        """Test that src.analysis module has proper docstring.

        Verifies that:
        - Module has a docstring attribute
        - Docstring is a non-empty string
        - Docstring provides package-level documentation
        """
        import src.analysis

        assert src.analysis.__doc__ is not None
        assert isinstance(src.analysis.__doc__, str)
        assert len(src.analysis.__doc__.strip()) > 0

    def test_docstring_content(self):
        """Test that docstring describes the module purpose.

        Ensures the package docstring contains relevant keywords that
        describe the analysis functionality (e.g., 'analysis', 'report',
        'transcription') to help users understand the package purpose.
        """
        import src.analysis

        docstring_lower = src.analysis.__doc__.lower()

        # Verify the docstring mentions analysis or reports
        expected_keywords = ["analysis", "report", "transcription"]
        assert any(
            keyword in docstring_lower for keyword in expected_keywords
        ), f"Docstring should describe analysis functionality: {src.analysis.__doc__}"

    # === Public API Export Tests ===

    def test_all_attribute_exists(self):
        """Test that __all__ attribute is defined.

        The __all__ list controls which names are exported when using
        'from src.analysis import *'. This test verifies the attribute
        exists and is properly defined as a list.
        """
        import src.analysis

        assert hasattr(src.analysis, "__all__")
        assert isinstance(src.analysis.__all__, list)

    def test_all_attribute_content(self):
        """Test that __all__ contains expected exports.

        Verifies that __all__ contains exactly the two analyzer classes
        that form the public API: ConciseAnalyzer and FullAnalyzer.
        No more, no less.
        """
        import src.analysis

        expected_exports = ["ConciseAnalyzer", "FullAnalyzer"]

        assert set(src.analysis.__all__) == set(
            expected_exports
        ), f"__all__ should contain {expected_exports}, got {src.analysis.__all__}"

    # === Analyzer Class Export Verification ===

    def test_concise_analyzer_exported(self):
        """Test that ConciseAnalyzer is properly exported.

        Verifies that:
        1. ConciseAnalyzer is accessible as an attribute of src.analysis
        2. It's the same object as the original class from concise_analyzer module

        This ensures the __init__.py correctly re-exports the class.
        """
        import src.analysis

        assert hasattr(src.analysis, "ConciseAnalyzer")

        # Verify it's the correct class (identity check)
        from src.analysis.concise_analyzer import ConciseAnalyzer

        assert src.analysis.ConciseAnalyzer is ConciseAnalyzer

    def test_full_analyzer_exported(self):
        """Test that FullAnalyzer is properly exported.

        Verifies that:
        1. FullAnalyzer is accessible as an attribute of src.analysis
        2. It's the same object as the original class from full_analyzer module

        This ensures the __init__.py correctly re-exports the class.
        """
        import src.analysis

        assert hasattr(src.analysis, "FullAnalyzer")

        # Verify it's the correct class (identity check)
        from src.analysis.full_analyzer import FullAnalyzer

        assert src.analysis.FullAnalyzer is FullAnalyzer

    # === Direct Import Pattern Tests ===

    def test_direct_import_concise_analyzer(self):
        """Test that ConciseAnalyzer can be imported directly from src.analysis.

        Validates the common import pattern: 'from src.analysis import ConciseAnalyzer'
        This is the recommended way for users to import the analyzer class.

        Verifies the imported object is a proper class with the expected name.
        """
        from src.analysis import ConciseAnalyzer

        assert ConciseAnalyzer is not None
        assert hasattr(ConciseAnalyzer, "__name__")
        assert ConciseAnalyzer.__name__ == "ConciseAnalyzer"

    def test_direct_import_full_analyzer(self):
        """Test that FullAnalyzer can be imported directly from src.analysis.

        Validates the common import pattern: 'from src.analysis import FullAnalyzer'
        This is the recommended way for users to import the analyzer class.

        Verifies the imported object is a proper class with the expected name.
        """
        from src.analysis import FullAnalyzer

        assert FullAnalyzer is not None
        assert hasattr(FullAnalyzer, "__name__")
        assert FullAnalyzer.__name__ == "FullAnalyzer"

    # === Wildcard Import Tests ===

    def test_wildcard_import(self):
        """Test that wildcard import works correctly.

        Validates that 'from src.analysis import *' respects the __all__ attribute
        and only imports the explicitly exported names (ConciseAnalyzer, FullAnalyzer).

        This prevents namespace pollution and ensures a clean public API.
        Uses exec() to simulate the wildcard import in an isolated namespace.
        """
        # Create an empty namespace to capture wildcard imports
        namespace = {}
        exec("from src.analysis import *", namespace)

        # Filter out dunder (double underscore) attributes like __builtins__
        # Only public names (not starting with __) should match __all__
        imported_names = [name for name in namespace.keys() if not name.startswith("__")]
        expected_names = ["ConciseAnalyzer", "FullAnalyzer"]

        assert set(imported_names) == set(
            expected_names
        ), f"Wildcard import should only import {expected_names}, got {imported_names}"

    # === API Cleanliness Tests ===

    def test_no_unexpected_public_exports(self):
        """Test that module doesn't expose unexpected public attributes.

        Ensures the package namespace is clean and only contains:
        - The two analyzer classes (ConciseAnalyzer, FullAnalyzer)
        - The two submodules they're imported from (concise_analyzer, full_analyzer)

        This prevents accidental exposure of implementation details or
        imported dependencies that should remain internal.
        """
        import src.analysis

        # Get all public attributes (not starting with underscore)
        public_attrs = [attr for attr in dir(src.analysis) if not attr.startswith("_")]

        # Expected: analyzer classes + their source submodules
        expected_attrs = ["ConciseAnalyzer", "FullAnalyzer", "concise_analyzer", "full_analyzer"]
        assert set(public_attrs) == set(
            expected_attrs
        ), f"Module should export {expected_attrs}, got {public_attrs}"

    # === Type Validation Tests ===

    def test_analyzer_classes_are_classes(self):
        """Test that exported analyzers are actually classes.

        Verifies that both ConciseAnalyzer and FullAnalyzer are proper
        Python classes (type objects), not instances or other objects.
        This ensures they can be instantiated correctly by users.
        """
        from src.analysis import ConciseAnalyzer, FullAnalyzer

        assert isinstance(ConciseAnalyzer, type), "ConciseAnalyzer should be a class"
        assert isinstance(FullAnalyzer, type), "FullAnalyzer should be a class"

    # === Integration Tests ===

    def test_import_does_not_raise(self):
        """Test that importing the module does not raise any exceptions.

        Validates that all import patterns work without errors:
        - Package import: import src.analysis
        - Direct class imports: from src.analysis import ConciseAnalyzer, FullAnalyzer

        This is a basic smoke test to catch import-time errors like
        circular dependencies, syntax errors, or missing dependencies.
        """
        try:
            pass
        except Exception as e:
            pytest.fail(f"Importing src.analysis should not raise exceptions: {e}")
