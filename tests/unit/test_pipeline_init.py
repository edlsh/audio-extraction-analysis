"""Test suite for pipeline package initialization."""


class TestPipelinePackage:
    """Test pipeline package module structure and exports."""

    def test_module_import(self):
        """Test that pipeline module can be imported successfully."""
        from src import pipeline

        assert pipeline is not None

    def test_process_pipeline_export(self):
        """Test that process_pipeline function is exported from pipeline."""
        from src.pipeline import process_pipeline

        assert callable(process_pipeline)

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        from src import pipeline

        assert hasattr(pipeline, "__all__")
        assert "process_pipeline" in pipeline.__all__
