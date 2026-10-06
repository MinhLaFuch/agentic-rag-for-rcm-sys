import gzip
import json

from package.data.loader import META_FIELDS, load_item_metadata


def _write_meta(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_load_item_metadata_filters_and_tags_domain(tmp_path):
    vg, toys = tmp_path / "vg.jsonl.gz", tmp_path / "toys.jsonl.gz"
    _write_meta(vg, [{"parent_asin": "a1", "title": "Game A", "extra": 1}, {"parent_asin": "a2", "title": "Game B"}])
    _write_meta(toys, [{"parent_asin": "t1", "title": "Toy"}])

    df = load_item_metadata(
        [("Video_Games", str(vg)), ("Toys_and_Games", str(toys))],
        keep=lambda domain, asin: asin != "a2",
    )

    assert list(df.columns) == META_FIELDS + ["domain"]
    assert sorted(zip(df["domain"], df["parent_asin"])) == [("Toys_and_Games", "t1"), ("Video_Games", "a1")]


def test_load_item_metadata_keeps_all_without_filter(tmp_path):
    path = tmp_path / "m.jsonl.gz"
    _write_meta(path, [{"parent_asin": "a1"}, {"parent_asin": "a2"}])
    assert len(load_item_metadata([("D", str(path))])) == 2
