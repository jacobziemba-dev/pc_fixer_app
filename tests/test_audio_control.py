from app.audio_control import PeakNormalizer, OutputDevice, match_device_id


def test_match_device_id_returns_known_id():
    devices = [
        OutputDevice(id="dev-a", name="Speakers", is_default=True),
        OutputDevice(id="dev-b", name="Headset", is_default=False),
    ]
    assert match_device_id(devices, "dev-b") == "dev-b"
    assert match_device_id(devices, "missing") == ""
    assert match_device_id(devices, "") == ""


def test_peak_normalizer_ducks_after_hot_frames():
    normalizer = PeakNormalizer(
        peak_threshold=0.9,
        hot_frames_required=5,
        cool_frames_required=8,
        duck_factor=0.7,
        volume_floor=0.2,
        recover_step=0.05,
    )
    normalizer.set_user_volume(100, 1.0)

    for _ in range(4):
        assert normalizer.process_peak(100, 0.95) is None

    ducked = normalizer.process_peak(100, 0.95)
    assert ducked is not None
    assert abs(ducked - 0.7) < 1e-6


def test_peak_normalizer_respects_volume_floor():
    normalizer = PeakNormalizer(
        peak_threshold=0.9,
        hot_frames_required=1,
        cool_frames_required=8,
        duck_factor=0.1,
        volume_floor=0.2,
    )
    normalizer.set_user_volume(42, 0.25)
    ducked = normalizer.process_peak(42, 1.0)
    assert ducked == 0.2


def test_peak_normalizer_never_exceeds_user_volume():
    normalizer = PeakNormalizer(
        peak_threshold=0.9,
        hot_frames_required=1,
        cool_frames_required=1,
        duck_factor=0.7,
        recover_step=0.5,
    )
    normalizer.set_user_volume(7, 0.4)
    ducked = normalizer.process_peak(7, 1.0)
    assert ducked is not None
    assert ducked <= 0.4

    # Cool frames recover toward user volume, not above it.
    recovered = normalizer.process_peak(7, 0.1)
    assert recovered is not None
    assert recovered <= 0.4


def test_peak_normalizer_recovers_after_cool_frames():
    normalizer = PeakNormalizer(
        peak_threshold=0.9,
        hot_frames_required=1,
        cool_frames_required=2,
        duck_factor=0.5,
        recover_step=0.25,
    )
    normalizer.set_user_volume(9, 1.0)
    assert normalizer.process_peak(9, 1.0) == 0.5

    assert normalizer.process_peak(9, 0.1) is None  # first cool frame
    recovered = normalizer.process_peak(9, 0.1)  # second cool frame
    assert recovered is not None
    assert abs(recovered - 0.75) < 1e-6

    assert normalizer.process_peak(9, 0.1) is None
    recovered_again = normalizer.process_peak(9, 0.1)
    assert recovered_again is not None
    assert abs(recovered_again - 1.0) < 1e-6


def test_peak_normalizer_prune_forgets_inactive_pids():
    normalizer = PeakNormalizer(hot_frames_required=1)
    normalizer.set_user_volume(1, 1.0)
    normalizer.set_user_volume(2, 0.8)
    normalizer.process_peak(1, 1.0)
    normalizer.prune({2})
    # PID 1 was pruned; a fresh duck starts from user volume again.
    normalizer.set_user_volume(1, 1.0)
    ducked = normalizer.process_peak(1, 1.0)
    assert ducked is not None
    assert abs(ducked - 0.7) < 1e-6
