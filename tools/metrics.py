"""分类评估度量 — compute_metrics/print_metrics (v2/v3 共享)

v4.0.1 从 v2/tools/eval_classify.py 提取 (v3/train|evaluate|clean_eval 依赖)。
"""

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")


def compute_metrics(results):
    matrix = {exp: {pred: 0 for pred in LABELS} for exp in LABELS}
    for expected, predicted in results:
        matrix[expected][predicted] += 1

    per_class = {}
    for lb in LABELS:
        tp = matrix[lb][lb]
        pred_total = sum(matrix[e][lb] for e in LABELS)
        exp_total = sum(matrix[lb][p] for p in LABELS)
        precision = tp / pred_total if pred_total > 0 else 0.0
        recall = tp / exp_total if exp_total > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_class[lb] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": exp_total,
        }

    correct = sum(matrix[lb][lb] for lb in LABELS)
    total = sum(sum(matrix[lb].values()) for lb in LABELS)
    accuracy = correct / total if total > 0 else 0.0

    macro_f1 = sum(per_class[lb]["f1"] for lb in LABELS) / len(LABELS)

    return {
        "confusion_matrix": matrix,
        "per_class": per_class,
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "total": total,
    }


def print_metrics(metrics, title=None):
    if title:
        print(title)
    print(f"  Total: {metrics['total']:,}  Accuracy: {metrics['accuracy']:.4f}  Macro-F1: {metrics['macro_f1']:.4f}")

    header = f"  {'':>10s}  {'precision':>10s}  {'recall':>10s}  {'f1':>10s}  {'support':>8s}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for lb in LABELS:
        p = metrics["per_class"][lb]
        print(f"  {lb:>10s}  {p['precision']:>10.4f}  {p['recall']:>10.4f}  {p['f1']:>10.4f}  {p['support']:>8}")

    print(f"\n  Confusion Matrix (rows=expected, cols=predicted):")
    print(f"  {'':>10s}  " + "".join(f"{lb:>10s}  " for lb in LABELS))
    for exp_lb in LABELS:
        row = f"  {exp_lb:>10s}  "
        for pred_lb in LABELS:
            row += f"{metrics['confusion_matrix'][exp_lb][pred_lb]:>10}  "
        print(row)
