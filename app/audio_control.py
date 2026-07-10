"""Windows per-app audio device routing and session volume helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# COM/WASAPI imports are deferred inside functions so unit tests can import
# PeakNormalizer without requiring a live Windows audio stack.


class AudioControlError(RuntimeError):
    """Raised when a Windows audio control operation fails."""


@dataclass(frozen=True)
class OutputDevice:
    id: str
    name: str
    is_default: bool = False


@dataclass(frozen=True)
class OutputSession:
    pid: int
    process_name: str
    display_name: str
    device_id: str
    device_name: str
    volume: float
    muted: bool


@dataclass(frozen=True)
class RouteResult:
    success: bool
    message: str
    pid: int = 0
    device_id: str = ""


def _require_windows_audio():
    try:
        import winappaudiorouter as war  # noqa: F401
        from pycaw.pycaw import AudioUtilities  # noqa: F401
    except ImportError as exc:
        raise AudioControlError(
            "Audio routing requires pycaw, comtypes, and winappaudiorouter. "
            "Install dependencies from requirements.txt."
        ) from exc


def list_output_devices() -> list[OutputDevice]:
    """Return active playback endpoints with friendly names."""
    _require_windows_audio()
    import winappaudiorouter as war

    try:
        devices = war.list_output_devices()
    except Exception as exc:
        raise AudioControlError(f"Could not enumerate playback devices: {exc}") from exc

    return [
        OutputDevice(id=device.id, name=device.name, is_default=bool(device.is_default))
        for device in devices
    ]


def list_output_sessions() -> list[OutputSession]:
    """Return apps with an active output audio session."""
    _require_windows_audio()
    import winappaudiorouter as war

    try:
        raw_sessions = war.list_app_sessions()
    except Exception as exc:
        raise AudioControlError(f"Could not enumerate audio sessions: {exc}") from exc

    volume_by_pid = _session_volume_map()
    sessions: list[OutputSession] = []
    seen_pids: set[int] = set()

    for raw in raw_sessions:
        pid = int(getattr(raw, "process_id", 0) or 0)
        if pid <= 0 or pid in seen_pids:
            continue
        seen_pids.add(pid)

        process_name = (getattr(raw, "process_name", None) or "").strip()
        if not process_name:
            process_name = f"pid-{pid}"

        volume, muted = volume_by_pid.get(pid, (1.0, False))
        device_id = getattr(raw, "device_id", "") or ""
        device_name = getattr(raw, "device_name", "") or ""
        display_name = _display_name_for_process(process_name, pid)

        sessions.append(
            OutputSession(
                pid=pid,
                process_name=process_name,
                display_name=display_name,
                device_id=device_id,
                device_name=device_name,
                volume=float(volume),
                muted=bool(muted),
            )
        )

    sessions.sort(key=lambda item: item.display_name.lower())
    return sessions


def get_app_output_device(*, process_id: int | None = None, process_name: str | None = None) -> dict[int, str]:
    """Return persisted per-app output device ids keyed by PID."""
    _require_windows_audio()
    import winappaudiorouter as war

    try:
        return dict(war.get_app_output_device(process_id=process_id, process_name=process_name) or {})
    except Exception as exc:
        raise AudioControlError(f"Could not read app output device: {exc}") from exc


def set_app_output_device(
    *,
    device: str,
    process_id: int | None = None,
    process_name: str | None = None,
) -> RouteResult:
    """Route an app to a playback device by PID or process name."""
    _require_windows_audio()
    import winappaudiorouter as war

    if not device:
        return RouteResult(False, "No target device was specified.", pid=process_id or 0)

    try:
        routed = war.set_app_output_device(
            process_id=process_id,
            process_name=process_name,
            device=device,
        )
    except Exception as exc:
        return RouteResult(
            False,
            f"Could not route audio: {exc}",
            pid=process_id or 0,
            device_id=device,
        )

    pid = process_id or (next(iter(routed), 0) if routed else 0)
    label = process_name or (f"PID {pid}" if pid else "app")
    return RouteResult(
        True,
        f"Routed {label} to the selected device. Some apps need a short pause/play to rebind.",
        pid=int(pid or 0),
        device_id=device,
    )


def clear_app_output_device(
    *,
    process_id: int | None = None,
    process_name: str | None = None,
) -> RouteResult:
    """Clear a persisted per-app route so the app uses the system default."""
    _require_windows_audio()
    import winappaudiorouter as war

    try:
        cleared = war.clear_app_output_device(process_id=process_id, process_name=process_name)
    except Exception as exc:
        return RouteResult(
            False,
            f"Could not clear app route: {exc}",
            pid=process_id or 0,
        )

    pid = process_id or (cleared[0] if cleared else 0)
    label = process_name or (f"PID {pid}" if pid else "app")
    return RouteResult(
        True,
        f"Restored {label} to the system default device.",
        pid=int(pid or 0),
        device_id="",
    )


def get_session_peak(pid: int) -> float:
    """Return the current peak meter value (0.0–1.0) for a process session."""
    session = _find_pycaw_session(pid)
    if session is None:
        return 0.0
    try:
        from pycaw.pycaw import IAudioMeterInformation

        meter = session._ctl.QueryInterface(IAudioMeterInformation)
        return float(meter.GetPeakValue())
    except Exception:
        return 0.0


def get_session_peaks(pids: list[int] | None = None) -> dict[int, float]:
    """Return peak values for the given PIDs (or all process sessions)."""
    wanted = set(pids) if pids is not None else None
    peaks: dict[int, float] = {}
    for session in _iter_pycaw_sessions():
        process = getattr(session, "Process", None)
        if process is None:
            continue
        try:
            pid = int(process.pid)
        except Exception:
            continue
        if wanted is not None and pid not in wanted:
            continue
        try:
            from pycaw.pycaw import IAudioMeterInformation

            meter = session._ctl.QueryInterface(IAudioMeterInformation)
            peaks[pid] = float(meter.GetPeakValue())
        except Exception:
            peaks[pid] = 0.0
    return peaks


def set_session_volume(pid: int, level: float) -> bool:
    """Set a session master volume scalar (0.0–1.0)."""
    session = _find_pycaw_session(pid)
    if session is None:
        return False
    try:
        clamped = max(0.0, min(1.0, float(level)))
        session.SimpleAudioVolume.SetMasterVolume(clamped, None)
        return True
    except Exception:
        return False


def set_session_mute(pid: int, muted: bool) -> bool:
    """Mute or unmute a session."""
    session = _find_pycaw_session(pid)
    if session is None:
        return False
    try:
        session.SimpleAudioVolume.SetMute(1 if muted else 0, None)
        return True
    except Exception:
        return False


def match_device_id(devices: list[OutputDevice], device_id: str) -> str:
    """Return a known device id, or empty string when unmatched / default."""
    if not device_id:
        return ""
    for device in devices:
        if device.id == device_id:
            return device.id
    return ""


@dataclass
class PeakNormalizerState:
    hot_frames: int = 0
    cool_frames: int = 0
    user_volume: float = 1.0
    effective_volume: float = 1.0
    ducked: bool = False


class PeakNormalizer:
    """Soft-limit loud session peaks without exceeding the user's set volume."""

    def __init__(
        self,
        *,
        peak_threshold: float = 0.9,
        hot_frames_required: int = 5,
        cool_frames_required: int = 8,
        duck_factor: float = 0.7,
        volume_floor: float = 0.2,
        recover_step: float = 0.05,
    ):
        self.peak_threshold = peak_threshold
        self.hot_frames_required = hot_frames_required
        self.cool_frames_required = cool_frames_required
        self.duck_factor = duck_factor
        self.volume_floor = volume_floor
        self.recover_step = recover_step
        self._states: dict[int, PeakNormalizerState] = {}

    def set_user_volume(self, pid: int, volume: float) -> None:
        state = self._state_for(pid)
        clamped = max(0.0, min(1.0, float(volume)))
        state.user_volume = clamped
        if not state.ducked:
            state.effective_volume = clamped
        else:
            state.effective_volume = min(state.effective_volume, clamped)

    def forget(self, pid: int) -> None:
        self._states.pop(pid, None)

    def prune(self, active_pids: set[int]) -> None:
        for pid in list(self._states):
            if pid not in active_pids:
                self.forget(pid)

    def process_peak(self, pid: int, peak: float, current_volume: float | None = None) -> float | None:
        """
        Feed one peak sample for a PID.

        Returns a new volume to apply, or None when no change is needed.
        """
        state = self._state_for(pid)
        if current_volume is not None and not state.ducked:
            # Keep user volume in sync when the mixer changes outside the guard.
            state.user_volume = max(0.0, min(1.0, float(current_volume)))
            state.effective_volume = state.user_volume

        if peak > self.peak_threshold:
            state.hot_frames += 1
            state.cool_frames = 0
        else:
            state.cool_frames += 1
            state.hot_frames = 0

        if state.hot_frames >= self.hot_frames_required:
            target = max(self.volume_floor, state.effective_volume * self.duck_factor)
            target = min(target, state.user_volume)
            state.hot_frames = 0
            if target < state.effective_volume - 1e-6:
                state.effective_volume = target
                state.ducked = True
                return state.effective_volume

        if state.ducked and state.cool_frames >= self.cool_frames_required:
            target = min(state.user_volume, state.effective_volume + self.recover_step)
            state.cool_frames = 0
            if target > state.effective_volume + 1e-6:
                state.effective_volume = target
                if state.effective_volume >= state.user_volume - 1e-6:
                    state.effective_volume = state.user_volume
                    state.ducked = False
                return state.effective_volume

        return None

    def _state_for(self, pid: int) -> PeakNormalizerState:
        if pid not in self._states:
            self._states[pid] = PeakNormalizerState()
        return self._states[pid]


def _display_name_for_process(process_name: str, pid: int) -> str:
    base = process_name
    if base.lower().endswith(".exe"):
        base = base[:-4]
    if not base:
        return f"PID {pid}"
    return f"{base} ({pid})"


def _session_volume_map() -> dict[int, tuple[float, bool]]:
    result: dict[int, tuple[float, bool]] = {}
    for session in _iter_pycaw_sessions():
        process = getattr(session, "Process", None)
        if process is None:
            continue
        try:
            pid = int(process.pid)
            volume = float(session.SimpleAudioVolume.GetMasterVolume())
            muted = bool(session.SimpleAudioVolume.GetMute())
            result[pid] = (volume, muted)
        except Exception:
            continue
    return result


def _find_pycaw_session(pid: int) -> Any | None:
    for session in _iter_pycaw_sessions():
        process = getattr(session, "Process", None)
        if process is None:
            continue
        try:
            if int(process.pid) == int(pid):
                return session
        except Exception:
            continue
    return None


def _iter_pycaw_sessions():
    _require_windows_audio()
    from pycaw.pycaw import AudioUtilities

    try:
        return AudioUtilities.GetAllSessions()
    except Exception:
        return []
