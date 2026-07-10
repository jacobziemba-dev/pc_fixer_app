import os

from app import system_info as sysinfo


def test_delete_cleanup_items_skips_paths_outside_category_roots(tmp_path, monkeypatch):
    allowed = tmp_path / "temp"
    unsafe = tmp_path / "documents"
    allowed.mkdir()
    unsafe.mkdir()
    keep_file = unsafe / "keep.txt"
    keep_file.write_text("keep", encoding="utf-8")

    monkeypatch.setattr(sysinfo, "_candidate_dirs", lambda: {
        "user_temp": ("User Temp Files", "Temporary files.", [str(allowed)]),
    })

    cat = sysinfo.CleanupCategory(
        key="user_temp",
        label="User Temp Files",
        description="Temporary files.",
        paths=[str(unsafe)],
        size_bytes=os.path.getsize(keep_file),
        file_count=1,
    )

    bytes_freed, errors = sysinfo.delete_cleanup_items([cat])

    assert bytes_freed == 0
    assert keep_file.exists()
    assert errors == [f"User Temp Files: skipped unsafe cleanup path {unsafe}"]


def test_delete_cleanup_items_allows_nested_paths_under_category_root(tmp_path, monkeypatch):
    allowed = tmp_path / "temp"
    nested = allowed / "nested"
    nested.mkdir(parents=True)
    junk_file = nested / "junk.txt"
    junk_file.write_text("junk", encoding="utf-8")

    monkeypatch.setattr(sysinfo, "_candidate_dirs", lambda: {
        "user_temp": ("User Temp Files", "Temporary files.", [str(allowed)]),
    })

    cat = sysinfo.CleanupCategory(
        key="user_temp",
        label="User Temp Files",
        description="Temporary files.",
        paths=[str(nested)],
        size_bytes=os.path.getsize(junk_file),
        file_count=1,
    )

    bytes_freed, errors = sysinfo.delete_cleanup_items([cat])

    assert bytes_freed == 4
    assert errors == []
    assert not junk_file.exists()
