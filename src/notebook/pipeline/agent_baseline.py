"""Backward-compatible wrapper for the shared package rerank baseline."""
from recommender.rerank import rerank

if __name__ == "__main__":
    candidates = [{"item_idx": 2, "title": "Bass String", "category": "Bass", "score": 0.007}]
    history = ["Guitar Pick Set", "Drum Sticks Pro", "Amp Cable"]
    result = rerank(history, candidates, use_mock=True)
    print("Kết quả rerank (mock LLM):")
    for r in result:
        print(f"  #{r['rank']} - item {r['item_idx']}: {r['reason']}")
