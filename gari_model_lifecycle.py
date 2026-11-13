# ==============================================================================
# GARI AgriTech AI Lab — On-Demand Model Lifecycle Manager
# Thread-safe, on-demand AI inference, per-model locking, LRU cache eviction,
# active request counting, and idle model auto-unloading.
# ==============================================================================

from __future__ import annotations

import collections
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
import gc
import logging
import os
import sys
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import psutil

logger = logging.getLogger("gari_lifecycle")


class ModelLifecycleState(str, Enum):
    UNLOADED = "UNLOADED"
    LOADING = "LOADING"
    READY = "READY"
    INFERENCE_ACTIVE = "INFERENCE_ACTIVE"
    UNLOADING = "UNLOADING"
    ERROR = "ERROR"


@dataclass
class LifecycleEvent:
    timestamp: float
    event_type: str
    model_id: str
    state: str
    active_requests: int
    duration_ms: float = 0.0
    memory_rss_mb: float = 0.0
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "iso_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp)),
            "event_type": self.event_type,
            "model_id": self.model_id,
            "state": self.state,
            "active_requests": self.active_requests,
            "duration_ms": round(self.duration_ms, 2),
            "memory_rss_mb": round(self.memory_rss_mb, 2),
            "details": self.details or {},
        }


def get_current_rss_mb() -> float:
    """Returns the current process resident set size (RSS) in megabytes."""
    try:
        proc = psutil.Process()
        return round(proc.memory_info().rss / (1024.0 * 1024.0), 2)
    except Exception:
        return 0.0


class ModelSlot:
    """
    Encapsulates state, synchronization, active references, and model instance
    for a single registered AI model.
    """

    def __init__(self, model_id: str, entry: Any = None):
        self.model_id = model_id
        self.entry = entry
        self.model: Optional[Any] = None
        self.state: ModelLifecycleState = ModelLifecycleState.UNLOADED
        self.active_requests: int = 0
        self.lock = threading.RLock()
        self.cond = threading.Condition(self.lock)
        self.last_used: float = 0.0
        self.load_time_ms: float = 0.0
        self.total_inferences: int = 0
        self.last_error: Optional[str] = None
        self.last_unloaded: float = 0.0

    def to_dict(self, sanitize: bool = True) -> Dict[str, Any]:
        idle_s = round(time.time() - self.last_used, 1) if self.last_used > 0 else 0.0
        data = {
            "model_id": self.model_id,
            "state": self.state.value,
            "is_loaded": self.model is not None,
            "active_requests": self.active_requests,
            "last_used_timestamp": self.last_used,
            "idle_duration_seconds": idle_s,
            "load_time_ms": round(self.load_time_ms, 2),
            "total_inferences": self.total_inferences,
            "last_error": self.last_error,
        }
        if not sanitize and self.entry is not None:
            data["entry_info"] = getattr(self.entry, "to_dict", lambda: str(self.entry))()
        return data


class ModelLifecycleManager:
    """
    Centralized Model Lifecycle Manager for GARI.
    Provides:
    - Lazy on-demand loading on first inference.
    - Model instance reuse across concurrent requests.
    - Per-model fine-grained locking (no global bottleneck during inference).
    - Active request tracking (prevents unloading while inference is running).
    - Strict LRU cache limit with active-request awareness.
    - Background idle cleanup loop with configurable timeout.
    - PyTorch CPU/CUDA garbage collection.
    - Full structured observability logging and event auditing.
    """

    def __init__(
        self,
        idle_timeout_seconds: Optional[float] = None,
        max_cached: Optional[int] = None,
        auto_unload_enabled: Optional[bool] = None,
        preload_enabled: Optional[bool] = None,
        cleanup_interval_seconds: Optional[float] = None,
    ):
        # Configuration with environment variable fallbacks
        self.idle_timeout_seconds = float(
            idle_timeout_seconds
            if idle_timeout_seconds is not None
            else os.getenv("MODEL_IDLE_TIMEOUT_SECONDS", "300")
        )
        self.max_cached = int(
            max_cached if max_cached is not None else os.getenv("MAX_CACHED_MODELS", "3")
        )
        self.auto_unload_enabled = bool(
            auto_unload_enabled
            if auto_unload_enabled is not None
            else os.getenv("MODEL_AUTO_UNLOAD_ENABLED", "true").lower() in ("true", "1", "yes")
        )
        self.preload_enabled = bool(
            preload_enabled
            if preload_enabled is not None
            else os.getenv("MODEL_PRELOAD_ENABLED", "false").lower() in ("true", "1", "yes")
        )

        # Cleanup interval adjusts dynamically for test environments with tiny timeouts
        if cleanup_interval_seconds is not None:
            self.cleanup_interval_seconds = float(cleanup_interval_seconds)
        else:
            env_interval = os.getenv("MODEL_CLEANUP_INTERVAL_SECONDS")
            if env_interval:
                self.cleanup_interval_seconds = float(env_interval)
            else:
                self.cleanup_interval_seconds = max(1.0, min(10.0, self.idle_timeout_seconds / 2.0))

        self._slots: Dict[str, ModelSlot] = {}
        self._global_lock = threading.RLock()
        self._events: collections.deque[LifecycleEvent] = collections.deque(maxlen=200)

        # Managed background cleanup thread
        self._cleaner_thread: Optional[threading.Thread] = None
        self._stop_cleaner_event = threading.Event()

        logger.info(
            "Initialized ModelLifecycleManager: max_cached=%d, idle_timeout=%.1fs, auto_unload=%s, preload=%s",
            self.max_cached,
            self.idle_timeout_seconds,
            self.auto_unload_enabled,
            self.preload_enabled,
        )

        if self.auto_unload_enabled:
            self.start_background_cleaner()

    def _record_event(
        self,
        event_type: str,
        model_id: str,
        state: str,
        active_requests: int,
        duration_ms: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> LifecycleEvent:
        rss_mb = get_current_rss_mb()
        event = LifecycleEvent(
            timestamp=time.time(),
            event_type=event_type,
            model_id=model_id,
            state=state,
            active_requests=active_requests,
            duration_ms=duration_ms,
            memory_rss_mb=rss_mb,
            details=details,
        )
        with self._global_lock:
            self._events.append(event)

        logger.info(
            "[MODEL_LIFECYCLE] event=%s model_id=%s state=%s active_requests=%d duration_ms=%.1f rss_mb=%.1f details=%s",
            event_type,
            model_id,
            state,
            active_requests,
            duration_ms,
            rss_mb,
            details or {},
        )
        return event

    def get_slot(self, model_id: str, entry: Any = None) -> ModelSlot:
        with self._global_lock:
            if model_id not in self._slots:
                self._slots[model_id] = ModelSlot(model_id, entry=entry)
            elif entry is not None and self._slots[model_id].entry is None:
                self._slots[model_id].entry = entry
            return self._slots[model_id]

    def _evict_lru_if_needed(self, needed_model_id: str) -> None:
        """
        Evicts the least recently used model from memory when loaded models count >= max_cached.
        CRITICAL: Never evicts a model that has active_requests > 0 or is currently INFERENCE_ACTIVE.
        """
        with self._global_lock:
            loaded_slots = [
                s for s in self._slots.values()
                if s.model is not None and s.model_id != needed_model_id
            ]
            if len(loaded_slots) < self.max_cached:
                return

            # Filter candidates: strictly active_requests == 0 and state == READY
            evictable = [
                s for s in loaded_slots
                if s.active_requests == 0 and s.state == ModelLifecycleState.READY
            ]

            while len([s for s in self._slots.values() if s.model is not None]) >= self.max_cached:
                if not evictable:
                    logger.warning(
                        "LRU eviction: all %d currently loaded models have active inference requests. Allowing soft limit burst.",
                        len(loaded_slots),
                    )
                    break

                # Pick the model with the oldest last_used timestamp
                oldest_slot = min(evictable, key=lambda s: s.last_used)
                evictable.remove(oldest_slot)
                logger.info(
                    "LRU evicting model '%s' (last_used=%.1fs ago, capacity=%d)",
                    oldest_slot.model_id,
                    time.time() - oldest_slot.last_used,
                    self.max_cached,
                )
                self._unload_slot_unlocked(oldest_slot, reason="lru_eviction")

    def load_model(
        self,
        model_id: str,
        loader_fn: Callable[[], Tuple[Any, Any]],
        entry: Any = None,
    ) -> Tuple[Any, Any]:
        """
        Loads a model into memory in READY state if not already loaded.
        If already loaded, reuses it immediately without touching active_requests.
        If currently loading by another thread, waits on condition variable.
        """
        slot = self.get_slot(model_id, entry)

        with slot.lock:
            # 1. If slot is currently unloading, wait until unload finishes
            while slot.state == ModelLifecycleState.UNLOADING:
                slot.cond.wait()

            # 2. If another thread is already loading this model, wait for it
            while slot.state == ModelLifecycleState.LOADING:
                logger.debug("Waiting for concurrent loading of model '%s'...", model_id)
                slot.cond.wait()

            # 3. If model is not loaded, load it now
            if slot.model is None or slot.state in (ModelLifecycleState.UNLOADED, ModelLifecycleState.ERROR):
                # Ensure LRU capacity before allocating new model weights
                self._evict_lru_if_needed(model_id)

                # Active Host RAM Safety Guard (Prevents host freeze/OOM crash)
                try:
                    vmem = psutil.virtual_memory()
                    # If physical RAM is above 90%, proactively evict all idle models and collect garbage
                    if vmem.percent > 90.0:
                        logger.warning(
                            "System RAM utilization elevated (%.1f%%). Triggering proactive idle model eviction before load...",
                            vmem.percent
                        )
                        self.check_and_unload_idle_models()
                        gc.collect()
                        # Only reject if available memory is below 200 MB or memory exceeds 98.5%
                        vmem_post = psutil.virtual_memory()
                        if vmem_post.available < 200 * 1024 * 1024 or vmem_post.percent > 98.5:
                            raise MemoryError(
                                f"System RAM critically saturated ({vmem_post.percent:.1f}%, available {vmem_post.available / (1024*1024):.1f} MB). Model load for '{model_id}' deferred to protect host stability."
                            )
                except Exception as guard_exc:
                    if isinstance(guard_exc, MemoryError):
                        raise

                slot.state = ModelLifecycleState.LOADING
                self._record_event(
                    "model_load_started",
                    model_id,
                    slot.state.value,
                    slot.active_requests,
                )

                t0 = time.perf_counter()
                try:
                    loaded_model, loaded_entry = loader_fn()
                    load_ms = (time.perf_counter() - t0) * 1000
                    slot.model = loaded_model
                    if loaded_entry is not None:
                        slot.entry = loaded_entry
                    slot.load_time_ms = load_ms
                    slot.last_used = time.time()
                    slot.last_error = None
                    slot.state = ModelLifecycleState.READY
                    slot.cond.notify_all()
                    self._record_event(
                        "model_load_completed",
                        model_id,
                        slot.state.value,
                        slot.active_requests,
                        duration_ms=load_ms,
                    )
                except Exception as exc:
                    slot.model = None
                    slot.state = ModelLifecycleState.ERROR
                    slot.last_error = str(exc)
                    slot.cond.notify_all()
                    slot.state = ModelLifecycleState.UNLOADED
                    self._record_event(
                        "model_load_failed",
                        model_id,
                        slot.state.value,
                        slot.active_requests,
                        details={"error": str(exc)},
                    )
                    raise

            return slot.model, slot.entry

    def acquire_for_inference(
        self,
        model_id: str,
        loader_fn: Callable[[], Tuple[Any, Any]],
        entry: Any = None,
    ) -> Tuple[Any, Any]:
        """
        Acquires a model specifically for active inference.
        Loads model if needed, marks state as INFERENCE_ACTIVE, and increments active_requests.
        """
        model, resolved_entry = self.load_model(model_id, loader_fn, entry)
        slot = self.get_slot(model_id)
        with slot.lock:
            slot.active_requests += 1
            slot.state = ModelLifecycleState.INFERENCE_ACTIVE
            slot.last_used = time.time()
            self._record_event(
                "inference_started",
                model_id,
                slot.state.value,
                slot.active_requests,
            )
        return model, resolved_entry

    def release_from_inference(self, model_id: str, infer_duration_ms: float = 0.0) -> None:
        """
        Releases a model after inference completes.
        Decrements active_requests counter and resets state to READY when active_requests reaches 0.
        """
        slot = self.get_slot(model_id)
        with slot.lock:
            slot.active_requests = max(0, slot.active_requests - 1)
            slot.total_inferences += 1
            slot.last_used = time.time()
            if slot.active_requests == 0:
                slot.state = ModelLifecycleState.READY

            self._record_event(
                "inference_completed",
                model_id,
                slot.state.value,
                slot.active_requests,
                duration_ms=infer_duration_ms,
            )
            slot.cond.notify_all()

    # Alias acquire_model to load_model for general calls
    acquire_model = load_model
    release_model = release_from_inference

    @contextmanager
    def use_model(
        self,
        model_id: str,
        loader_fn: Callable[[], Tuple[Any, Any]],
        entry: Any = None,
    ) -> Iterator[Tuple[Any, Any]]:
        """
        Safe context manager for on-demand inference.
        Guarantees that active_requests is decremented even if an exception occurs during inference.
        """
        model, resolved_entry = self.acquire_for_inference(model_id, loader_fn, entry)
        t_start = time.perf_counter()
        try:
            yield model, resolved_entry
        finally:
            infer_ms = (time.perf_counter() - t_start) * 1000.0
            self.release_from_inference(model_id, infer_duration_ms=infer_ms)

    def _unload_slot_unlocked(self, slot: ModelSlot, reason: str = "explicit") -> bool:
        """
        Unloads a slot safely. Acquires slot.lock (re-entrant).
        Returns True if unloaded, False if skipped.
        """
        with slot.lock:
            if slot.model is None or slot.state == ModelLifecycleState.UNLOADED:
                return False

            if slot.active_requests > 0:
                logger.warning(
                    "Cannot unload model '%s': active inference in progress (active_requests=%d, reason=%s)",
                    slot.model_id,
                    slot.active_requests,
                    reason,
                )
                return False

            idle_duration = time.time() - slot.last_used if slot.last_used > 0 else 0.0
            slot.state = ModelLifecycleState.UNLOADING
            self._record_event(
                "model_unload_started",
                slot.model_id,
                slot.state.value,
                slot.active_requests,
                details={"reason": reason, "idle_duration_s": round(idle_duration, 2)},
            )

            t0 = time.perf_counter()
            try:
                # Release PyTorch references
                model_ref = slot.model
                slot.model = None
                del model_ref

                # Garbage collect unreferenced objects
                gc.collect()

                # Optional CUDA cache cleanup
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

                unload_ms = (time.perf_counter() - t0) * 1000
                slot.state = ModelLifecycleState.UNLOADED
                slot.last_unloaded = time.time()
                slot.cond.notify_all()

                self._record_event(
                    "model_unload_completed",
                    slot.model_id,
                    slot.state.value,
                    slot.active_requests,
                    duration_ms=unload_ms,
                    details={"reason": reason, "idle_duration_s": round(idle_duration, 2)},
                )
                return True
            except Exception as exc:
                slot.state = ModelLifecycleState.ERROR
                slot.last_error = str(exc)
                slot.cond.notify_all()
                self._record_event(
                    "model_unload_failed",
                    slot.model_id,
                    slot.state.value,
                    slot.active_requests,
                    details={"error": str(exc)},
                )
                slot.state = ModelLifecycleState.UNLOADED
                return False

    def unload_model(self, model_id: str, reason: str = "explicit", force: bool = False) -> bool:
        """
        Explicitly unloads a specific model if active_requests == 0.
        """
        with self._global_lock:
            if model_id not in self._slots:
                return False
            slot = self._slots[model_id]

        with slot.lock:
            if force:
                slot.active_requests = 0
            return self._unload_slot_unlocked(slot, reason=reason)

    def unload_all(self, reason: str = "explicit") -> int:
        """
        Unloads all models currently loaded in memory with active_requests == 0.
        Returns the number of models successfully unloaded.
        """
        unloaded_count = 0
        with self._global_lock:
            slots = list(self._slots.values())

        for slot in slots:
            with slot.lock:
                if slot.model is not None and slot.active_requests == 0:
                    if self._unload_slot_unlocked(slot, reason=reason):
                        unloaded_count += 1
        return unloaded_count

    def check_and_unload_idle_models(self) -> List[str]:
        """
        Inspects all loaded models and unloads those whose idle duration >= idle_timeout_seconds.
        """
        unloaded = []
        now = time.time()

        with self._global_lock:
            slots = list(self._slots.values())

        for slot in slots:
            with slot.lock:
                if (
                    slot.model is not None
                    and slot.active_requests == 0
                    and slot.state == ModelLifecycleState.READY
                ):
                    idle_s = now - slot.last_used
                    if idle_s >= self.idle_timeout_seconds:
                        logger.info(
                            "Model '%s' idle timeout expired (idle=%.1fs >= limit=%.1fs). Unloading.",
                            slot.model_id,
                            idle_s,
                            self.idle_timeout_seconds,
                        )
                        if self._unload_slot_unlocked(slot, reason="idle_timeout"):
                            unloaded.append(slot.model_id)
        return unloaded

    def _idle_cleanup_loop(self) -> None:
        """Background daemon loop that periodically purges idle models."""
        logger.info("Model lifecycle cleanup loop started (interval: %.1fs)", self.cleanup_interval_seconds)
        while not self._stop_cleaner_event.wait(self.cleanup_interval_seconds):
            if not self.auto_unload_enabled:
                continue
            try:
                self.check_and_unload_idle_models()
            except Exception as exc:
                logger.error("Unexpected error in model lifecycle cleanup loop: %s", exc)

    def start_background_cleaner(self) -> None:
        if self._cleaner_thread is None or not self._cleaner_thread.is_alive():
            self._stop_cleaner_event.clear()
            self._cleaner_thread = threading.Thread(
                target=self._idle_cleanup_loop,
                name="GariModelLifecycleCleaner",
                daemon=True,
            )
            self._cleaner_thread.start()

    def stop_background_cleaner(self, timeout: float = 2.0) -> None:
        self._stop_cleaner_event.set()
        if self._cleaner_thread and self._cleaner_thread.is_alive():
            self._cleaner_thread.join(timeout=timeout)

    def get_lifecycle_status(self, include_all_registered: bool = False) -> Dict[str, Any]:
        """
        Returns full diagnostic status for administrative monitoring.
        Sanitizes all internal paths to prevent security disclosure.
        """
        now = time.time()
        with self._global_lock:
            slots_snapshot = list(self._slots.values())

        loaded_models = []
        all_models = []
        active_inferences_total = 0

        for slot in sorted(slots_snapshot, key=lambda s: s.model_id):
            slot_dict = slot.to_dict(sanitize=True)
            active_inferences_total += slot.active_requests
            if slot.model is not None:
                loaded_models.append(slot_dict)
            all_models.append(slot_dict)

        return {
            "status": "healthy",
            "memory_rss_mb": get_current_rss_mb(),
            "config": {
                "max_cached_models": self.max_cached,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "auto_unload_enabled": self.auto_unload_enabled,
                "preload_enabled": self.preload_enabled,
                "cleanup_interval_seconds": self.cleanup_interval_seconds,
            },
            "loaded_count": len(loaded_models),
            "active_inferences_total": active_inferences_total,
            "loaded_models": loaded_models,
            "all_slots_count": len(all_models),
            "models": all_models if include_all_registered else loaded_models,
        }

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._global_lock:
            events = list(self._events)
        return [e.to_dict() for e in events[-limit:]]
