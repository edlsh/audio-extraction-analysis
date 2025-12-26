"""Model caching for Parakeet ASR models."""

from __future__ import annotations

import asyncio
import time
from threading import Lock
from typing import Any

from src.exceptions import ParakeetModelError
from src.utils.constants import Limits
from src.utils.logger import get_logger

from .deps import TORCH_AVAILABLE, _ensure_nemo, nemo_asr
from .gpu import GPUManager

logger = get_logger(__name__)

# Module-level constants
MAX_CACHE_SIZE: int = Limits.PARAKEET_MAX_CACHE_SIZE  # Maximum number of models to cache


class ParakeetModelCache:
    """Singleton cache for Parakeet ASR models.

    Implements LRU caching with GPU memory management.
    Thread-safe singleton initialization using double-checked locking pattern.
    """

    _instance: ParakeetModelCache | None = None
    _lock = Lock()  # Lock for singleton creation
    _init_lock = Lock()  # Lock for instance initialization

    def __new__(cls) -> ParakeetModelCache:
        """Ensure singleton pattern with thread-safe double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    # Set _initialized early to prevent races from __init__
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the cache (called once, thread-safe)."""
        # Fast path: avoid lock acquisition if already initialized
        if self._initialized:
            return

        # Thread-safe initialization using a separate lock
        with self._init_lock:
            # Double-check after acquiring lock
            if self._initialized:
                return

            self._models: dict[str, tuple[Any, float]] = {}
            self._model_sizes: dict[str, int] = {}
            self._max_cache_size = MAX_CACHE_SIZE
            self._cache_lock = Lock()
            self._loading_locks: dict[str, Lock] = {}
            self._gpu_manager = GPUManager()
            self._initialized = True

            logger.info(f"ParakeetModelCache initialized with device: {self._gpu_manager.device}")

    def __init__(self) -> None:
        """Initialize cache if not already done.

        Note: After __new__ returns, _initialized is already set to False,
        so we call _initialize() which handles thread-safe lazy initialization.
        """
        # Fast path: avoid any work if already initialized
        if self._initialized:
            return
        self._initialize()

    def get_model(self, model_name: str, force_reload: bool = False) -> Any | None:
        """Get a model from cache or load it."""
        if not _ensure_nemo():
            logger.error("NeMo toolkit not available")
            return None

        loading_lock = self._get_or_create_loading_lock(model_name)

        with loading_lock:
            cached = self._get_cached_model(model_name, force_reload)
            if cached is not None:
                return cached

            return self._load_and_cache_model(model_name)

    def _get_or_create_loading_lock(self, model_name: str) -> Lock:
        """Get or create a loading lock for a specific model."""
        with self._cache_lock:
            if model_name not in self._loading_locks:
                self._loading_locks[model_name] = Lock()
            return self._loading_locks[model_name]

    def _get_cached_model(self, model_name: str, force_reload: bool) -> Any | None:
        """Check cache for model. Returns model if found, None otherwise."""
        with self._cache_lock:
            if not force_reload and model_name in self._models:
                model, _ = self._models[model_name]
                self._models[model_name] = (model, time.time())
                logger.debug(f"Model {model_name} retrieved from cache")
                return model
        return None

    def _load_and_cache_model(self, model_name: str) -> Any | None:
        """Load model and add to cache."""
        try:
            logger.info(f"Loading model {model_name}...")
            model = self._load_model_sync(model_name)

            if model is not None:
                model_size = self._estimate_model_size(model_name)
                self._ensure_gpu_space(model_name, model_size)
                self._add_to_cache(model_name, model, model_size)

            return model

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise ParakeetModelError(f"Failed to load model {model_name}: {e}")

    def _ensure_gpu_space(self, model_name: str, model_size: int) -> None:
        """Ensure GPU has space for model, evicting if necessary."""
        if not self._gpu_manager.can_allocate_model(model_size):
            logger.warning(f"Insufficient GPU memory for model {model_name}")
            self._evict_models_for_space(model_size, self._gpu_manager)

    def _add_to_cache(self, model_name: str, model: Any, model_size: int) -> None:
        """Add model to cache, enforcing size limits."""
        with self._cache_lock:
            self._enforce_cache_limit()
            self._models[model_name] = (model, time.time())
            self._model_sizes[model_name] = model_size
            logger.info(
                f"Model {model_name} added to cache (cache size: {len(self._models)}/{MAX_CACHE_SIZE})"
            )

    def _enforce_cache_limit(self) -> None:
        """Remove LRU model if cache is at capacity. Must hold _cache_lock."""
        if len(self._models) >= self._max_cache_size:
            lru_model = min(self._models.items(), key=lambda x: x[1][1])
            del self._models[lru_model[0]]
            if lru_model[0] in self._model_sizes:
                del self._model_sizes[lru_model[0]]
            logger.info(f"Evicted model {lru_model[0]} from cache (LRU)")

    async def get_model_async(self, model_name: str, force_reload: bool = False) -> Any | None:
        """Async wrapper for get_model."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_model, model_name, force_reload)

    def _load_model_sync(self, model_name: str) -> Any:
        """Synchronously load a Parakeet model."""
        if not self._is_valid_model_name(model_name):
            raise ValueError(f"Invalid model name: {model_name}")

        try:
            if not _ensure_nemo():
                raise RuntimeError("NeMo not available")
            model = nemo_asr.models.ASRModel.from_pretrained(model_name)
            if TORCH_AVAILABLE and self._gpu_manager.device != "cpu":
                model = model.to(self._gpu_manager.device)
            model.eval()
            return model
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            raise

    def _is_valid_model_name(self, model_name: str) -> bool:
        """Validate model name format."""
        return bool(model_name and isinstance(model_name, str))

    def _estimate_model_size(self, model_name: str) -> int:
        """Estimate model size in bytes."""
        size_map = {
            "stt_en_fastconformer_transducer_large": 600 * 1024 * 1024,
            "stt_en_conformer_transducer_large": 500 * 1024 * 1024,
            "stt_en_conformer_transducer_medium": 300 * 1024 * 1024,
            "stt_en_conformer_transducer_small": 150 * 1024 * 1024,
        }
        return size_map.get(model_name, 400 * 1024 * 1024)

    def _evict_models_for_space(self, required_size: int, gpu_manager: GPUManager) -> None:
        """Evict models to free up space."""
        with self._cache_lock:
            if not self._models:
                return

            sorted_models = sorted(self._models.items(), key=lambda x: x[1][1])

            freed_space = 0
            models_to_evict = []

            for model_name, (_model, _last_used) in sorted_models:
                if freed_space >= required_size:
                    break

                model_size = self._model_sizes.get(model_name, 0)
                models_to_evict.append(model_name)
                freed_space += model_size

            for model_name in models_to_evict:
                del self._models[model_name]
                if model_name in self._model_sizes:
                    del self._model_sizes[model_name]
                logger.info(f"Evicted model {model_name} to free GPU memory")

            if models_to_evict:
                gpu_manager.cleanup_gpu_memory()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            total_size = sum(self._model_sizes.values())
            return {
                "cached_models": len(self._models),
                "model_names": list(self._models.keys()),
                "total_size_mb": total_size / (1024 * 1024),
                "max_cache_size": self._max_cache_size,
                "device": self._gpu_manager.device if hasattr(self, "_gpu_manager") else "unknown",
            }


__all__ = ["ParakeetModelCache"]
