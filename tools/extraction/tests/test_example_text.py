"""نص كل مثال من مقاطعه: التجميع بالدرس والمثال وترتيب التتمة، بقارئ وهمي بلا OCR."""

from tools.extraction.example_text import collect


def test_collect_groups_by_example_and_appends_continuation(tmp_path):
    for name in ("1.1_m1_p10.png", "1.1_m2_p11.png", "1.1_m1_p11_cont.png", "notes.png"):
        (tmp_path / name).write_bytes(b"x")

    got = collect(tmp_path, tmp_path / "cache", lambda path, cache: [(path.stem.split("_")[2], [0, 0, 1, 1])])

    assert got == {"1.1": {"1": "p10 p11", "2": "p11"}}
