"""Measure cross-domain user coverage from cleaned and temporal split artifacts."""

import argparse
import json
from itertools import combinations
from pathlib import Path

import matplotlib
import pyarrow.compute as pc
import pyarrow.parquet as pq

matplotlib.use("Agg")
from matplotlib import pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
DOMAINS = ("Video_Games", "Toys_and_Games", "Electronics")


def read_users(path, domains, cutoff=None):
    users = {domain: set() for domain in domains}
    columns = ["user_id"]
    if len(domains) > 1:
        columns.append("domain")
    if cutoff is not None:
        columns.append("timestamp")
    for batch in pq.ParquetFile(path).iter_batches(columns=columns):
        if cutoff is not None:
            batch = batch.filter(pc.less_equal(batch["timestamp"], cutoff))
        for domain in domains:
            ids = batch["user_id"]
            if "domain" in columns:
                ids = pc.filter(ids, pc.equal(batch["domain"], domain))
            users[domain].update(value for value in pc.unique(ids).to_pylist() if value)
    print(f"Read {path}", flush=True)
    return users


def ratio(count, total):
    return count / total if total else None


def intersection(left, right):
    if len(left) > len(right):
        left, right = right, left
    return sum(user in right for user in left)


def summarize(users):
    sizes = {domain: len(ids) for domain, ids in users.items()}
    overlap = {domain: {domain: size} for domain, size in sizes.items()}
    for left, right in combinations(users, 2):
        count = intersection(users[left], users[right])
        overlap[left][right] = overlap[right][left] = count
    smallest, second, third = sorted(users.values(), key=len)
    all_three = sum(user in second and user in third for user in smallest)
    pair_sum = sum(overlap[a][b] for a, b in combinations(users, 2))
    exactly_two = pair_sum - 3 * all_three
    exactly_one = sum(sizes.values()) - 2 * exactly_two - 3 * all_three
    union = exactly_one + exactly_two + all_three
    multi = exactly_two + all_three
    ablations = {}
    for removed in users:
        a, b = (domain for domain in users if domain != removed)
        pair_multi = overlap[a][b]
        pair_union = sizes[a] + sizes[b] - pair_multi
        ablations[removed] = dict(
            unique_users=pair_union, multidomain_users=pair_multi,
            multidomain_fraction=ratio(pair_multi, pair_union),
            lost_unique_users=union - pair_union, lost_multidomain_users=multi - pair_multi,
        )
    return dict(
        users_per_domain=sizes, overlap_counts=overlap,
        overlap_fraction_by_row={
            a: {b: ratio(overlap[a][b], sizes[a]) for b in users} for a in users
        },
        exact_domain_counts={1: exactly_one, 2: exactly_two, 3: all_three},
        exact_domain_fractions={1: ratio(exactly_one, union), 2: ratio(exactly_two, union),
                                3: ratio(all_three, union)},
        unique_users=union, multidomain_users=multi, multidomain_fraction=ratio(multi, union),
        leave_one_domain_out=ablations,
    )


def plot_counts(results, output):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for ax, (label, summary) in zip(axes, results.items()):
        counts = summary["exact_domain_counts"]
        bars = ax.bar(list(counts), list(counts.values()), color="#267673")
        ax.bar_label(bars, labels=[f"{n:,}" for n in counts.values()], padding=3)
        ax.set_xticks([1, 2, 3])
        ax.set_ylim(0, max(1, max(counts.values()) * 1.18))
        ax.set(title=label, xlabel="Number of domains", ylabel="Unique users")
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", type=Path, default=ROOT / "resource")
    parser.add_argument("--tag", default="multi_domain_v2_audit_20261030")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments" / "user_id_coverage")
    parser.add_argument("--candidate-trio", nargs=3, action="append", default=[],
                        help="Compare another trio using cleaned parquet at the same cutoff")
    args = parser.parse_args()
    for trio in args.candidate_trio:
        if len(set(trio)) != 3:
            parser.error("Each candidate trio must contain three distinct domains")
    split_dir = args.resource / "splits" / args.tag
    manifest = json.loads((split_dir / "stage_3.manifest.json").read_text(encoding="utf-8"))
    cutoff = manifest["flags"]["cutoff_1"]

    def cleaned_summary(domains):
        users = {}
        for domain in domains:
            path = args.resource / "cleaned" / domain / "interactions.parquet"
            users.update(read_users(path, (domain,), cutoff))
        return summarize(users)

    before = cleaned_summary(DOMAINS)
    train = read_users(split_dir / "train_core.parquet", DOMAINS)
    after = summarize(train)
    targets = read_users(split_dir / "test.parquet", DOMAINS)
    test_coverage = {}
    for domain, ids in targets.items():
        other_a, other_b = (train[other] for other in DOMAINS if other != domain)
        covered = sum(user in other_a or user in other_b for user in ids)
        test_coverage[domain] = dict(
            test_users=len(ids), users_with_other_domain_train_core=covered,
            fraction=ratio(covered, len(ids)),
        )
    del train, targets
    result = dict(
        split_tag=args.tag, train_cutoff_inclusive_ms=cutoff,
        cleaned_before_filter=before, train_core=after, test_coverage=test_coverage,
        candidate_trios_before_filter=[
            dict(domains=trio, **cleaned_summary(trio)) for trio in args.candidate_trio
        ],
    )
    args.output.mkdir(parents=True, exist_ok=True)
    plot_counts({"Cleaned before filtering": before, "Train core": after},
                args.output / "domain_counts.png")
    (args.output / "coverage.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Results: {args.output}")


if __name__ == "__main__":
    main()
