import gzip
import json

from package.data.loader.iter_jsonl_gz import iter_jsonl_gz


def test_iter_jsonl_reads_plain_jsonl(tmp_path):
    path = tmp_path / "metadata.jsonl"
    path.write_text(json.dumps({"parent_asin": "item-1"}) + "\n", encoding="utf-8")
    assert list(iter_jsonl_gz(path)) == [{"parent_asin": "item-1"}]


def test_iter_jsonl_reads_gzip_jsonl(tmp_path):
    path = tmp_path / "metadata.jsonl"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps({"parent_asin": "item-2"}) + "\n")
    assert list(iter_jsonl_gz(path)) == [{"parent_asin": "item-2"}]
