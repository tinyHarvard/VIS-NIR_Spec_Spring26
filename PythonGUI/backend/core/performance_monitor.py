from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import perf_counter
from typing import Iterator

DEFAULT_PERFORMANCE_SAMPLE_COUNT = 480
DEFAULT_PERFORMANCE_TARGET_RATE_HZ = 125.0


@dataclass(frozen=True)
class PerformanceMetricSnapshot:
    """Purpose: describe one recent timing metric. Rationale: formatting and sorting are easier when metrics have a stable public shape."""
    name: str
    recent_samples: int
    total_samples: int
    avg_ms: float
    p95_ms: float
    max_ms: float
    rate_hz: float
    load_ms_per_s: float


@dataclass(frozen=True)
class PerformanceValueSnapshot:
    """Purpose: describe one rolling numeric signal. Rationale: queue depth, frame age, and frame interval are values, not timings, but still need recent summaries."""
    name: str
    recent_samples: int
    total_samples: int
    avg_value: float
    p95_value: float
    min_value: float
    max_value: float
    latest_value: float
    sample_rate_hz: float


@dataclass(frozen=True)
class PerformanceCounterSnapshot:
    """Purpose: describe one rolling counter stream. Rationale: bytes, frames, and missed-frame events need per-second rates and totals, not timing stats."""
    name: str
    recent_events: int
    total_count: float
    recent_total: float
    rate_per_s: float


class _MetricWindow:
    """Purpose: store recent samples for one metric. Rationale: timing summaries should use a bounded rolling window instead of unbounded history."""
    def __init__(self, *, max_samples: int) -> None:
        self.durations_ms: deque[float] = deque(maxlen=max_samples)
        self.timestamps_s: deque[float] = deque(maxlen=max_samples)
        self.total_samples = 0


class _ValueWindow:
    """Purpose: store recent numeric samples for one signal. Rationale: rolling stream-health values should use the same bounded-window behavior as timing metrics."""
    def __init__(self, *, max_samples: int) -> None:
        self.values: deque[float] = deque(maxlen=max_samples)
        self.timestamps_s: deque[float] = deque(maxlen=max_samples)
        self.total_samples = 0


class _CounterWindow:
    """Purpose: store recent counter deltas for one event stream. Rationale: byte throughput and missed-frame counts need rolling rates without unbounded history."""
    def __init__(self, *, max_samples: int) -> None:
        self.amounts: deque[float] = deque(maxlen=max_samples)
        self.timestamps_s: deque[float] = deque(maxlen=max_samples)
        self.total_count = 0.0


class PerformanceMonitor:
    """Purpose: collect lightweight rolling timing metrics across threads. Rationale: performance work needs real numbers from both the backend worker and the UI thread."""
    def __init__(self, *, max_samples: int = DEFAULT_PERFORMANCE_SAMPLE_COUNT) -> None:
        self._max_samples = max(int(max_samples), 8)
        self._lock = Lock()
        self._enabled = True
        self._metrics: dict[str, _MetricWindow] = {}
        self._values: dict[str, _ValueWindow] = {}
        self._counters: dict[str, _CounterWindow] = {}

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        """Purpose: time one code block. Rationale: context managers make call-site instrumentation short and consistent."""
        if not self._enabled:
            yield
            return
        start_s = perf_counter()
        try:
            yield
        finally:
            self.record_duration(name, perf_counter() - start_s)

    def set_enabled(self, enabled: bool) -> None:
        """Purpose: enable or pause metric collection. Rationale: the performance tooling should be removable from the hot path when the user hides the readout."""
        self._enabled = bool(enabled)

    def reset(self) -> None:
        """Purpose: clear all rolling metrics. Rationale: fresh profiling sessions should start from an empty window when the readout is re-enabled."""
        with self._lock:
            self._metrics.clear()
            self._values.clear()
            self._counters.clear()

    def record_duration(self, name: str, duration_s: float) -> None:
        """Purpose: store one completed duration sample. Rationale: some hot paths are easier to instrument with manual timing than with a context manager."""
        if not self._enabled:
            return
        duration_ms = max(float(duration_s), 0.0) * 1000.0
        sample_time_s = perf_counter()
        with self._lock:
            metric = self._metrics.get(name)
            if metric is None:
                metric = _MetricWindow(max_samples=self._max_samples)
                self._metrics[name] = metric
            metric.durations_ms.append(duration_ms)
            metric.timestamps_s.append(sample_time_s)
            metric.total_samples += 1

    def record_value(self, name: str, value: float) -> None:
        """Purpose: store one numeric sample that is not itself a duration. Rationale: frame interval, queue depth, and frame age help explain throughput limits that timings alone cannot show."""
        if not self._enabled:
            return
        sample_value = float(value)
        sample_time_s = perf_counter()
        with self._lock:
            metric = self._values.get(name)
            if metric is None:
                metric = _ValueWindow(max_samples=self._max_samples)
                self._values[name] = metric
            metric.values.append(sample_value)
            metric.timestamps_s.append(sample_time_s)
            metric.total_samples += 1

    def increment(self, name: str, amount: float = 1.0) -> None:
        """Purpose: record one counter increment. Rationale: throughput-style metrics such as bytes-per-second and frames-per-second are easier to understand as event counts over time."""
        if not self._enabled:
            return
        increment_amount = float(amount)
        if increment_amount == 0.0:
            return
        sample_time_s = perf_counter()
        with self._lock:
            metric = self._counters.get(name)
            if metric is None:
                metric = _CounterWindow(max_samples=self._max_samples)
                self._counters[name] = metric
            metric.amounts.append(increment_amount)
            metric.timestamps_s.append(sample_time_s)
            metric.total_count += increment_amount

    @staticmethod
    def _rate_from_timestamps(timestamps_s: list[float], event_count: int) -> float:
        """Purpose: turn rolling timestamps into a recent per-second rate. Rationale: timing, value, and counter windows all need the same rate calculation."""
        if len(timestamps_s) < 2 or event_count <= 0:
            return 0.0
        elapsed_s = max(timestamps_s[-1] - timestamps_s[0], 1e-9)
        return event_count / elapsed_s

    def snapshot(self) -> list[PerformanceMetricSnapshot]:
        """Purpose: return recent timing summaries. Rationale: the UI should render a consistent snapshot without holding the monitor lock during formatting."""
        with self._lock:
            raw_metrics = [
                (
                    name,
                    list(metric.durations_ms),
                    list(metric.timestamps_s),
                    metric.total_samples,
                )
                for name, metric in self._metrics.items()
            ]

        snapshots: list[PerformanceMetricSnapshot] = []
        for name, durations_ms, timestamps_s, total_samples in raw_metrics:
            if not durations_ms:
                continue
            sorted_durations = sorted(durations_ms)
            sample_count = len(sorted_durations)
            p95_index = max(min(ceil(sample_count * 0.95) - 1, sample_count - 1), 0)
            avg_ms = sum(sorted_durations) / sample_count
            p95_ms = sorted_durations[p95_index]
            max_ms = sorted_durations[-1]
            rate_hz = self._rate_from_timestamps(timestamps_s, len(timestamps_s) - 1)
            snapshots.append(
                PerformanceMetricSnapshot(
                    name=name,
                    recent_samples=sample_count,
                    total_samples=total_samples,
                    avg_ms=avg_ms,
                    p95_ms=p95_ms,
                    max_ms=max_ms,
                    rate_hz=rate_hz,
                    load_ms_per_s=avg_ms * rate_hz,
                )
            )

        snapshots.sort(
            key=lambda item: (item.load_ms_per_s, item.avg_ms, item.p95_ms, item.name),
            reverse=True,
        )
        return snapshots

    def snapshot_values(self) -> list[PerformanceValueSnapshot]:
        """Purpose: return recent summaries for numeric signals. Rationale: stream-health values should be rendered in one stable snapshot alongside timings."""
        with self._lock:
            raw_values = [
                (
                    name,
                    list(metric.values),
                    list(metric.timestamps_s),
                    metric.total_samples,
                )
                for name, metric in self._values.items()
            ]

        snapshots: list[PerformanceValueSnapshot] = []
        for name, values, timestamps_s, total_samples in raw_values:
            if not values:
                continue
            sorted_values = sorted(values)
            sample_count = len(sorted_values)
            p95_index = max(min(ceil(sample_count * 0.95) - 1, sample_count - 1), 0)
            snapshots.append(
                PerformanceValueSnapshot(
                    name=name,
                    recent_samples=sample_count,
                    total_samples=total_samples,
                    avg_value=sum(values) / sample_count,
                    p95_value=sorted_values[p95_index],
                    min_value=sorted_values[0],
                    max_value=sorted_values[-1],
                    latest_value=values[-1],
                    sample_rate_hz=self._rate_from_timestamps(timestamps_s, len(timestamps_s) - 1),
                )
            )

        snapshots.sort(
            key=lambda item: (item.avg_value, item.p95_value, item.name),
            reverse=True,
        )
        return snapshots

    def snapshot_counters(self) -> list[PerformanceCounterSnapshot]:
        """Purpose: return recent summaries for counter-style metrics. Rationale: throughput limits often show up as event rates long before timings alone look alarming."""
        with self._lock:
            raw_counters = [
                (
                    name,
                    list(metric.amounts),
                    list(metric.timestamps_s),
                    metric.total_count,
                )
                for name, metric in self._counters.items()
            ]

        snapshots: list[PerformanceCounterSnapshot] = []
        for name, amounts, timestamps_s, total_count in raw_counters:
            if not amounts:
                continue
            recent_total = sum(amounts)
            rate_per_s = self._rate_from_timestamps(timestamps_s, 0)
            if len(timestamps_s) >= 2:
                elapsed_s = max(timestamps_s[-1] - timestamps_s[0], 1e-9)
                rate_per_s = recent_total / elapsed_s
            snapshots.append(
                PerformanceCounterSnapshot(
                    name=name,
                    recent_events=len(amounts),
                    total_count=total_count,
                    recent_total=recent_total,
                    rate_per_s=rate_per_s,
                )
            )

        snapshots.sort(
            key=lambda item: (item.rate_per_s, item.recent_total, item.name),
            reverse=True,
        )
        return snapshots

    @staticmethod
    def _find_timing_metric(
        snapshots: list[PerformanceMetricSnapshot],
        metric_name: str,
    ) -> PerformanceMetricSnapshot | None:
        """Purpose: look up one timing metric by name. Rationale: the summary header needs stable access to a few key metrics without repeated scan logic."""
        return next((metric for metric in snapshots if metric.name == metric_name), None)

    @staticmethod
    def _find_value_metric(
        snapshots: list[PerformanceValueSnapshot],
        metric_name: str,
    ) -> PerformanceValueSnapshot | None:
        """Purpose: look up one value metric by name. Rationale: key stream-health lines should be built from named metrics when they exist."""
        return next((metric for metric in snapshots if metric.name == metric_name), None)

    @staticmethod
    def _find_counter_metric(
        snapshots: list[PerformanceCounterSnapshot],
        metric_name: str,
    ) -> PerformanceCounterSnapshot | None:
        """Purpose: look up one counter metric by name. Rationale: throughput sections need direct access to bytes-per-second and frames-per-second counters."""
        return next((metric for metric in snapshots if metric.name == metric_name), None)

    def format_report(
        self,
        *,
        max_metrics: int = 8,
        max_values: int = 6,
        max_counters: int = 6,
        target_rate_hz: float = DEFAULT_PERFORMANCE_TARGET_RATE_HZ,
    ) -> str:
        """Purpose: render a concise performance report for the UI. Rationale: a readable summary should explain both where time is spent and why the stream may fail to sustain the target rate."""
        timing_snapshots = self.snapshot()
        value_snapshots = self.snapshot_values()
        counter_snapshots = self.snapshot_counters()
        if not timing_snapshots and not value_snapshots and not counter_snapshots:
            return "Performance Snapshot\nNo timing samples recorded yet."

        target_rate_hz = max(float(target_rate_hz), 1e-9)
        target_frame_budget_ms = 1000.0 / target_rate_hz
        lines = [
            "Performance Snapshot",
            f"125 Hz analysis target: {target_rate_hz:.1f} Hz | {target_frame_budget_ms:.2f} ms/frame budget",
        ]

        frame_interval_metric = self._find_value_metric(value_snapshots, "backend.frame_interval_ms")
        chunk_interval_metric = self._find_value_metric(value_snapshots, "transport.read_chunk_interval_ms")
        chunk_size_metric = self._find_value_metric(value_snapshots, "transport.read_chunk_bytes")
        queue_wait_metric = self._find_value_metric(value_snapshots, "backend.bytes_queue_wait_ms")
        queue_depth_metric = self._find_value_metric(value_snapshots, "backend.bytes_queue_depth")
        frame_age_metric = self._find_value_metric(value_snapshots, "ui.latest_frame_age_ms")
        refresh_interval_metric = self._find_value_metric(value_snapshots, "ui.refresh_plot_interval_ms")
        plot_interval_metric = self._find_value_metric(value_snapshots, "ui.plot_update_interval_ms")
        frame_counter_metric = self._find_counter_metric(counter_snapshots, "backend.frames_processed")
        byte_counter_metric = self._find_counter_metric(counter_snapshots, "transport.bytes_in")
        missed_counter_metric = self._find_counter_metric(counter_snapshots, "backend.frames_missed")
        refresh_plot_counter = self._find_counter_metric(counter_snapshots, "ui.refresh_plot_calls")
        plot_update_counter = self._find_counter_metric(counter_snapshots, "ui.plot_updates")
        spectrum_update_counter = self._find_counter_metric(counter_snapshots, "ui.live_spectrum_updates")
        spectrogram_update_counter = self._find_counter_metric(counter_snapshots, "ui.live_spectrogram_updates")
        spectrogram_skip_counter = self._find_counter_metric(counter_snapshots, "ui.spectrogram_refresh_skips")
        paused_skip_counter = self._find_counter_metric(counter_snapshots, "ui.refresh_plot_paused_skips")
        no_frame_counter = self._find_counter_metric(counter_snapshots, "ui.refresh_plot_no_frame")
        session_overwrite_counter = self._find_counter_metric(counter_snapshots, "backend.session_frame_overwrites")
        spectrogram_overwrite_counter = self._find_counter_metric(counter_snapshots, "backend.spectrogram_history_overwrites")

        selected_pipeline_metrics = [
            metric
            for metric_name in (
                "backend.packet_parse",
                "backend.frame_process",
                "backend.build_from_frame",
                "backend.build_processed_columns",
                "ui.refresh_plot",
                "ui.live_spectrum_redraw",
                "ui.live_spectrogram_texture_build",
                "ui.live_spectrogram_redraw",
                "ui.live_x_axis_redraw",
                "ui.live_y_axis_redraw",
            )
            if (metric := self._find_timing_metric(timing_snapshots, metric_name)) is not None
        ]
        if selected_pipeline_metrics:
            limiting_metric = max(selected_pipeline_metrics, key=lambda item: item.avg_ms)
            limiting_budget_percent = (limiting_metric.avg_ms / target_frame_budget_ms) * 100.0
            lines.append(
                "Likely 125 Hz limiter: "
                f"{limiting_metric.name} avg {limiting_metric.avg_ms:.2f} ms "
                f"({limiting_budget_percent:.1f}% of frame budget)"
            )

        if frame_interval_metric is not None and frame_interval_metric.avg_value > 0.0:
            observed_rate_hz = 1000.0 / frame_interval_metric.avg_value
            lines.append(
                "Observed stream: "
                f"{observed_rate_hz:5.1f} Hz avg | "
                f"interval avg {frame_interval_metric.avg_value:6.2f} ms | "
                f"p95 {frame_interval_metric.p95_value:6.2f} ms"
            )
        elif frame_counter_metric is not None:
            lines.append(
                "Observed stream: "
                f"{frame_counter_metric.rate_per_s:5.1f} frames/s | "
                f"total {frame_counter_metric.total_count:.0f}"
            )

        transport_parts: list[str] = []
        if chunk_interval_metric is not None:
            transport_parts.append(
                f"interval avg {chunk_interval_metric.avg_value:5.2f} ms p95 {chunk_interval_metric.p95_value:5.2f}"
            )
        if chunk_size_metric is not None:
            transport_parts.append(
                f"bytes avg {chunk_size_metric.avg_value:6.1f} p95 {chunk_size_metric.p95_value:6.1f}"
            )
        if transport_parts:
            lines.append("Transport chunks: " + " | ".join(transport_parts))

        queue_parts: list[str] = []
        if queue_wait_metric is not None:
            queue_parts.append(
                f"wait avg {queue_wait_metric.avg_value:5.2f} ms p95 {queue_wait_metric.p95_value:5.2f}"
            )
        if queue_depth_metric is not None:
            queue_parts.append(
                f"depth avg {queue_depth_metric.avg_value:5.2f} max {queue_depth_metric.max_value:5.0f}"
            )
        if queue_parts:
            lines.append("Queue pressure: " + " | ".join(queue_parts))

        if frame_age_metric is not None:
            lines.append(
                "Display age: "
                f"avg {frame_age_metric.avg_value:6.2f} ms | "
                f"p95 {frame_age_metric.p95_value:6.2f} | "
                f"latest {frame_age_metric.latest_value:6.2f}"
            )

        throughput_parts: list[str] = []
        if byte_counter_metric is not None:
            throughput_parts.append(f"bytes {byte_counter_metric.rate_per_s:7.0f}/s")
        if frame_counter_metric is not None:
            throughput_parts.append(f"frames {frame_counter_metric.rate_per_s:5.1f}/s")
        if missed_counter_metric is not None:
            throughput_parts.append(f"missed {missed_counter_metric.rate_per_s:5.2f}/s")
        if throughput_parts:
            lines.append("Throughput: " + " | ".join(throughput_parts))

        cadence_parts: list[str] = []
        if refresh_plot_counter is not None:
            cadence_parts.append(f"refresh {refresh_plot_counter.rate_per_s:5.1f}/s")
        if plot_update_counter is not None:
            cadence_parts.append(f"paint {plot_update_counter.rate_per_s:5.1f}/s")
        if spectrum_update_counter is not None:
            cadence_parts.append(f"line {spectrum_update_counter.rate_per_s:5.1f}/s")
        if spectrogram_update_counter is not None:
            cadence_parts.append(f"spec {spectrogram_update_counter.rate_per_s:5.1f}/s")
        if spectrogram_skip_counter is not None:
            cadence_parts.append(f"spec skipped {spectrogram_skip_counter.rate_per_s:5.1f}/s")
        if refresh_interval_metric is not None:
            cadence_parts.append(f"refresh dt {refresh_interval_metric.avg_value:5.2f} ms")
        if plot_interval_metric is not None:
            cadence_parts.append(f"paint dt {plot_interval_metric.avg_value:5.2f} ms")
        if cadence_parts:
            lines.append("UI cadence: " + " | ".join(cadence_parts))

        loss_parts: list[str] = []
        if missed_counter_metric is not None and missed_counter_metric.rate_per_s > 0.0:
            loss_parts.append(f"missed {missed_counter_metric.rate_per_s:5.2f}/s")
        if session_overwrite_counter is not None and session_overwrite_counter.rate_per_s > 0.0:
            loss_parts.append(f"session overwrite {session_overwrite_counter.rate_per_s:5.2f}/s")
        if spectrogram_overwrite_counter is not None and spectrogram_overwrite_counter.rate_per_s > 0.0:
            loss_parts.append(f"spec overwrite {spectrogram_overwrite_counter.rate_per_s:5.2f}/s")
        if no_frame_counter is not None and no_frame_counter.rate_per_s > 0.0:
            loss_parts.append(f"empty refresh {no_frame_counter.rate_per_s:5.2f}/s")
        if paused_skip_counter is not None and paused_skip_counter.rate_per_s > 0.0:
            loss_parts.append(f"paused skip {paused_skip_counter.rate_per_s:5.2f}/s")
        if loss_parts:
            lines.append("Loss / skip signals: " + " | ".join(loss_parts))

        if selected_pipeline_metrics:
            lines.append("Pipeline budget checkpoints")
        for metric in selected_pipeline_metrics[: max(int(max_metrics), 1)]:
            budget_percent = (metric.avg_ms / target_frame_budget_ms) * 100.0
            sustainable_rate_hz = 1000.0 / max(metric.avg_ms, 1e-9)
            lines.append(
                (
                    f"{metric.name:<30} "
                    f"avg {metric.avg_ms:6.2f} ms | "
                    f"budget {budget_percent:6.1f}% | "
                    f"ceiling {sustainable_rate_hz:6.1f} Hz"
                )
            )

        if timing_snapshots:
            lines.append("Per-event 125 Hz budget guide (if one call had to run every frame)")
        for metric in sorted(timing_snapshots, key=lambda item: (item.avg_ms, item.name), reverse=True)[: max(int(max_metrics), 1)]:
            budget_percent = (metric.avg_ms / target_frame_budget_ms) * 100.0
            sustainable_rate_hz = 1000.0 / max(metric.avg_ms, 1e-9)
            lines.append(
                (
                    f"{metric.name:<30} "
                    f"avg {metric.avg_ms:6.2f} ms | "
                    f"budget {budget_percent:6.1f}% | "
                    f"ceiling {sustainable_rate_hz:6.1f} Hz"
                )
            )

        if timing_snapshots:
            lines.append("Top recent timing load (avg ms x calls/sec)")
        for metric in timing_snapshots[: max(int(max_metrics), 1)]:
            lines.append(
                (
                    f"{metric.name:<30} "
                    f"avg {metric.avg_ms:6.2f} ms | "
                    f"p95 {metric.p95_ms:6.2f} | "
                    f"max {metric.max_ms:6.2f} | "
                    f"rate {metric.rate_hz:5.1f}/s | "
                    f"load {metric.load_ms_per_s:7.1f}"
                )
            )

        if value_snapshots:
            lines.append("Key stream signals")
        for metric in value_snapshots[: max(int(max_values), 1)]:
            lines.append(
                (
                    f"{metric.name:<30} "
                    f"avg {metric.avg_value:7.2f} | "
                    f"p95 {metric.p95_value:7.2f} | "
                    f"latest {metric.latest_value:7.2f} | "
                    f"max {metric.max_value:7.2f}"
                )
            )

        if counter_snapshots:
            lines.append("Event counters")
        for metric in counter_snapshots[: max(int(max_counters), 1)]:
            lines.append(
                (
                    f"{metric.name:<30} "
                    f"rate {metric.rate_per_s:8.2f}/s | "
                    f"recent {metric.recent_total:8.2f} | "
                    f"total {metric.total_count:10.2f}"
                )
            )
        return "\n".join(lines)
