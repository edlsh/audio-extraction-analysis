"""Test suite for pipeline package initialization."""

import pytest


class TestPipelinePackage:
    """Test pipeline package module structure and exports."""

    def test_module_import(self):
        """Test that pipeline module can be imported successfully."""
        from src import pipeline
        assert pipeline is not None

    def test_module_docstring(self):
        """Test that pipeline module has proper docstring."""
        from src import pipeline
        assert pipeline.__doc__ is not None
        assert isinstance(pipeline.__doc__, str)
        assert len(pipeline.__doc__.strip()) > 0

    def test_audio_processing_pipeline_export(self):
        """Test that AudioProcessingPipeline is exported from pipeline."""
        from src.pipeline import AudioProcessingPipeline

        # Verify it's a class
        assert isinstance(AudioProcessingPipeline, type)

        # Verify it's the correct class from audio_pipeline module
        from src.pipeline.audio_pipeline import AudioProcessingPipeline as DirectImport
        assert AudioProcessingPipeline is DirectImport

    def test_process_pipeline_export(self):
        """Test that process_pipeline function is exported from pipeline."""
        from src.pipeline import process_pipeline

        # Verify it's a callable
        assert callable(process_pipeline)

        # Verify it's the correct function from simple_pipeline module
        from src.pipeline.simple_pipeline import process_pipeline as DirectImport
        assert process_pipeline is DirectImport

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        from src import pipeline

        # Verify __all__ exists
        assert hasattr(pipeline, '__all__')
        assert isinstance(pipeline.__all__, list)

        # Verify expected items are in __all__
        expected_exports = ["AudioProcessingPipeline", "process_pipeline"]
        assert set(pipeline.__all__) == set(expected_exports)

        # Verify all items in __all__ are actually accessible
        for export_name in pipeline.__all__:
            assert hasattr(pipeline, export_name), \
                f"{export_name} is in __all__ but not accessible"

    def test_wildcard_import(self):
        """Test that wildcard import works correctly."""
        # This simulates: from src.pipeline import *
        from src import pipeline

        namespace = {}
        for name in pipeline.__all__:
            namespace[name] = getattr(pipeline, name)

        # Verify expected items are in namespace
        assert "AudioProcessingPipeline" in namespace
        assert "process_pipeline" in namespace

        # Verify they are the correct types
        assert isinstance(namespace["AudioProcessingPipeline"], type)
        assert callable(namespace["process_pipeline"])

    def test_no_unexpected_public_exports(self):
        """Test that only expected items are publicly exported."""
        from src import pipeline

        # Get all public attributes (not starting with _)
        public_attrs = [attr for attr in dir(pipeline) if not attr.startswith('_')]

        # Expected public attributes (beyond __all__ items)
        expected_attrs = set(pipeline.__all__)

        # Allow module attributes that are imported submodules
        # (e.g., audio_pipeline, simple_pipeline might be visible)
        actual_attrs = set(public_attrs)

        # All items in __all__ should be present
        for expected in expected_attrs:
            assert expected in actual_attrs, \
                f"Expected export '{expected}' not found in public attributes"

    def test_audio_processing_pipeline_is_class(self):
        """Test that AudioProcessingPipeline is a proper class."""
        from src.pipeline import AudioProcessingPipeline

        # Verify it has expected attributes/methods
        assert hasattr(AudioProcessingPipeline, '__init__')
        assert hasattr(AudioProcessingPipeline, '__doc__')

        # Verify class docstring exists
        assert AudioProcessingPipeline.__doc__ is not None
        assert isinstance(AudioProcessingPipeline.__doc__, str)

    def test_process_pipeline_is_async_function(self):
        """Test that process_pipeline is an async function."""
        from src.pipeline import process_pipeline
        import asyncio

        # Verify it's a coroutine function
        assert asyncio.iscoroutinefunction(process_pipeline), \
            "process_pipeline should be an async function"

    def test_direct_vs_package_import_equivalence(self):
        """Test that importing from package is same as direct import."""
        # Import from package
        from src.pipeline import AudioProcessingPipeline, process_pipeline

        # Import directly from modules
        from src.pipeline.audio_pipeline import AudioProcessingPipeline as DirectPipeline
        from src.pipeline.simple_pipeline import process_pipeline as DirectProcess

        # Verify they're the same objects
        assert AudioProcessingPipeline is DirectPipeline
        assert process_pipeline is DirectProcess

    def test_package_name_and_path(self):
        """Test that package has correct name and path attributes."""
        from src import pipeline

        assert pipeline.__name__ == "src.pipeline"
        assert hasattr(pipeline, '__file__') or hasattr(pipeline, '__path__')

    def test_docstring_content(self):
        """Test that docstring contains expected content."""
        from src import pipeline

        expected_keywords = ["pipeline", "audio", "transcription", "workflow"]
        docstring_lower = pipeline.__doc__.lower()

        # Verify the docstring mentions relevant concepts
        assert any(keyword in docstring_lower for keyword in expected_keywords), \
            f"Docstring should mention pipeline/audio concepts: {pipeline.__doc__}"

    def test_audio_processing_pipeline_deprecation_warning(self):
        """Test that AudioProcessingPipeline emits deprecation warning on instantiation."""
        import warnings
        from src.pipeline import AudioProcessingPipeline

        # Capture deprecation warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Instantiate the deprecated class
            pipeline = AudioProcessingPipeline()
            
            # Verify deprecation warning was emitted
            assert len(w) > 0, "Expected deprecation warning to be emitted"
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "process_pipeline" in str(w[0].message)
