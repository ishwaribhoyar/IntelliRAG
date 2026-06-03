# Trust Layer Validation

## Formula
```
confidence = 0.4 * norm_vec + 0.3 * norm_rrf + 0.3 * agreement
```

## Calibration Results (Dataset A)

| Level | Threshold | Count | Correct | Accuracy |
|:---|:---:|:---:|:---:|:---:|
| high | > 0.7 | 47 | 45 | 95.7% |
| medium | 0.4-0.7 | 10 | 7 | 70.0% |
| low | < 0.4 | 3 | 3 | 100.0% |
