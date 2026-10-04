import pandas as pd
import pytest

from package.data import (
    ITEM_ID_SEPARATOR,
    namespaced_item_id,
)
from package.data.domain import (
    domain_breakdown,
    merge_domains,
    tag_domain,
)


@pytest.fixture
def video_games_df():
    return pd.DataFrame(
        {
            "user_id": ["u1", "u2"],
            "parent_asin": ["ASIN_X", "ASIN_Y"],
            "rating": [5.0, 4.0],
            "timestamp": [100, 200],
        }
    )


@pytest.fixture
def toys_games_df():
    # Cố tình dùng "ASIN_X" TRÙNG với video_games_df để test chống collision.
    # u1 xuất hiện lại (đúng thiết kế: user_id global, cùng 1 user thật
    # mua cả game và đồ chơi).
    return pd.DataFrame(
        {
            "user_id": ["u1", "u3"],
            "parent_asin": ["ASIN_X", "ASIN_Z"],
            "rating": [3.0, 5.0],
            "timestamp": [150, 250],
        }
    )


def test_namespaced_item_id_format():
    assert namespaced_item_id("Video_Games", "ASIN_X") == f"Video_Games{ITEM_ID_SEPARATOR}ASIN_X"


def test_tag_domain_adds_correct_columns(video_games_df):
    tagged = tag_domain(video_games_df, "Video_Games")
    assert (tagged["domain"] == "Video_Games").all()
    assert list(tagged["original_item_id"]) == ["ASIN_X", "ASIN_Y"]
    assert list(tagged["parent_asin"]) == [f"Video_Games{ITEM_ID_SEPARATOR}ASIN_X", f"Video_Games{ITEM_ID_SEPARATOR}ASIN_Y"]
    # user_id KHÔNG bị đổi (thiết kế có chủ đích — global user id)
    assert list(tagged["user_id"]) == ["u1", "u2"]


def test_tag_domain_raises_without_parent_asin_column():
    bad_df = pd.DataFrame({"user_id": ["u1"]})
    with pytest.raises(ValueError):
        tag_domain(bad_df, "Video_Games")


def test_merge_domains_prevents_id_collision(video_games_df, toys_games_df):
    """
    Test QUAN TRỌNG NHẤT: cả 2 domain đều có raw parent_asin='ASIN_X'.
    Nếu không namespace đúng, 2 item hoàn toàn khác nhau (1 video game,
    1 món đồ chơi) sẽ bị hệ thống hiểu nhầm là CÙNG 1 item.
    """
    tagged_vg = tag_domain(video_games_df, "Video_Games")
    tagged_tg = tag_domain(toys_games_df, "Toys_and_Games")
    merged = merge_domains([tagged_vg, tagged_tg])

    namespaced_ids = set(merged["parent_asin"])
    assert f"Video_Games{ITEM_ID_SEPARATOR}ASIN_X" in namespaced_ids
    assert f"Toys_and_Games{ITEM_ID_SEPARATOR}ASIN_X" in namespaced_ids
    # 2 item id namespaced phải KHÁC NHAU dù raw asin giống nhau
    assert f"Video_Games{ITEM_ID_SEPARATOR}ASIN_X" != f"Toys_and_Games{ITEM_ID_SEPARATOR}ASIN_X"
    # tổng số dòng đúng bằng tổng 2 domain (không mất/nhân đôi dữ liệu)
    assert len(merged) == len(video_games_df) + len(toys_games_df)


def test_merge_domains_preserves_shared_user_id_across_domains(video_games_df, toys_games_df):
    """
    u1 xuất hiện ở CẢ 2 domain — đây chính là cơ chế giảm cold-start
    (D-010). Verify user_id không bị namespace/đổi, để hệ thống nhận ra
    đây là CÙNG 1 user.
    """
    tagged_vg = tag_domain(video_games_df, "Video_Games")
    tagged_tg = tag_domain(toys_games_df, "Toys_and_Games")
    merged = merge_domains([tagged_vg, tagged_tg])

    u1_rows = merged[merged["user_id"] == "u1"]
    assert len(u1_rows) == 2
    assert set(u1_rows["domain"]) == {"Video_Games", "Toys_and_Games"}


def test_merge_domains_raises_if_not_tagged(video_games_df):
    with pytest.raises(ValueError):
        merge_domains([video_games_df])  # chưa tag_domain()


def test_merge_domains_raises_on_empty_list():
    with pytest.raises(ValueError):
        merge_domains([])


def test_domain_breakdown_counts_correctly(video_games_df, toys_games_df):
    tagged_vg = tag_domain(video_games_df, "Video_Games")
    tagged_tg = tag_domain(toys_games_df, "Toys_and_Games")
    merged = merge_domains([tagged_vg, tagged_tg])

    breakdown = domain_breakdown(merged).set_index("domain")
    assert breakdown.loc["Video_Games", "num_interactions"] == 2
    assert breakdown.loc["Toys_and_Games", "num_interactions"] == 2
    assert breakdown.loc["Video_Games", "num_users"] == 2
    assert breakdown.loc["Toys_and_Games", "num_users"] == 2
