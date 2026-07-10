from app import system_info as sysinfo


def test_supported_refresh_rates_filter_dedupe_and_sort():
    current = sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=180)
    modes = [
        sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=60),
        sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=180),
        sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=144),
        sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=144),
        sysinfo.DisplayMode(width=1920, height=1080, bit_depth=8, refresh_hz=240),
        sysinfo.DisplayMode(width=2560, height=1440, bit_depth=10, refresh_hz=120),
        sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=1),
    ]

    assert sysinfo._supported_refresh_rates_for_modes(current, modes) == [60, 144, 180]


def test_supported_refresh_rates_includes_current_when_modes_miss_it():
    current = sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=165)
    modes = [
        sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=60),
        sysinfo.DisplayMode(width=2560, height=1440, bit_depth=8, refresh_hz=144),
    ]

    assert sysinfo._supported_refresh_rates_for_modes(current, modes) == [60, 144, 165]


def test_result_message_maps_common_win32_codes():
    assert sysinfo._result_message(sysinfo.win32con.DISP_CHANGE_SUCCESSFUL) == (
        "Refresh rate changed successfully."
    )
    assert "not supported" in sysinfo._result_message(sysinfo.win32con.DISP_CHANGE_BADMODE)
    assert "requires a restart" in sysinfo._result_message(sysinfo.win32con.DISP_CHANGE_RESTART)
    assert "code 12345" in sysinfo._result_message(12345)


def test_monitor_name_from_edid_descriptor():
    edid = bytearray(128)
    descriptor_offset = 54
    edid[descriptor_offset:descriptor_offset + 5] = b"\x00\x00\x00\xfc\x00"
    edid[descriptor_offset + 5:descriptor_offset + 18] = b"Q27G3XMN\n".ljust(13, b" ")

    assert sysinfo._monitor_name_from_edid(bytes(edid)) == "Q27G3XMN"
