from pathlib import Path
from triad.patcher.patches import PATCHES, StringPatch
from triad.patcher.apply import apply_string_patch


def test_patches_have_required_fields():
    for patch in PATCHES:
        assert patch.file
        assert patch.find
        assert patch.replace
        assert patch.description


def test_patch_count():
    assert len(PATCHES) >= 5


def test_apply_string_patch_replaces(tmp_path: Path):
    test_file = tmp_path / "test.js"
    test_file.write_text('var url = "https://chatgpt.com/backend-api";')

    patch = StringPatch(
        file="test.js",
        find="https://chatgpt.com/backend-api",
        replace="http://127.0.0.1:9377/api",
        description="test",
    )

    result = apply_string_patch(tmp_path, patch)
    assert result is True
    assert "127.0.0.1:9377" in test_file.read_text()
    assert "chatgpt.com" not in test_file.read_text()


def test_apply_string_patch_missing_file(tmp_path: Path):
    patch = StringPatch(file="missing.js", find="x", replace="y", description="test")
    result = apply_string_patch(tmp_path, patch)
    assert result is False


def test_apply_string_patch_pattern_not_found(tmp_path: Path):
    test_file = tmp_path / "test.js"
    test_file.write_text("var x = 1;")

    patch = StringPatch(file="test.js", find="not_here", replace="y", description="test")
    result = apply_string_patch(tmp_path, patch)
    assert result is False
