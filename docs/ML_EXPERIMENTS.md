# Offline detection experiments

The API never trains on import. It loads `backend/app/ml/artifacts/manifest.json`; missing or invalid artifacts produce explicit `RULES` mode.

Run the reproducible application-security experiment from the repository root:

```powershell
python -m backend.app.ml.experiments prepare
python -m backend.app.ml.experiments train
python -m backend.app.ml.experiments evaluate
# or all three
python -m backend.app.ml.experiments all
```

Preparation validates the schema, splits before preprocessing, and records the seed and SHA-256 checksum. The toy fixture has no timestamps, users, devices, sessions, or synthetic-run groups, so the report explicitly records that group/time separation is unavailable. Datasets containing `synthetic_run_id` are rejected until a group-aware split is supplied. Preprocessing is fitted inside each training pipeline. Random Forest and histogram gradient boosting use identical features and validation rows. Validation selects the model and binary attack threshold. Isolation Forest is fitted only to normal training rows; its exported novelty score is `-decision_function`, so higher is more anomalous. The reserved test set is evaluated only during the final command.

The exported report contains class support, macro F1, per-class precision/recall, confusion matrix, attack PR-AUC, false-positive rate, p50/p95 single-row inference latency, hardware context, dependency versions, schemas, thresholds, seeds, checksums, and saved predictions. Results from the 40-row synthetic fixture are labelled toy results and do not support a generalization or target-accuracy claim.

Application event detection uses server-derived login/audit windows. IoMT network integrity and physiological signal quality are separate outputs. Authorization remains deterministic and cannot be bypassed by an ML score.

## Optional CICIoMT2024 adapter

Download CICIoMT2024 yourself from the [University of New Brunswick CIC dataset site](https://www.unb.ca/cic/datasets/index.html). Review its terms, preserve the dataset/paper citation, place extracted CSV files in `datasets/ciciomt2024/raw`, and save the reviewed terms as `datasets/ciciomt2024/LICENSE_OR_TERMS.txt`. Then run:

```powershell
python -m backend.app.ml.ciciomt2024_adapter --accept-terms
```

The adapter verifies the expected network-flow schema and writes only network features plus the source label. It never converts network columns into login events, clinical measurements, or clinical ground truth. Without locally supplied data and accepted terms, the benchmark reports `NOT_RUN`.
