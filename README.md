# Finstream MetaOpt

Adaptive machine learning system for streaming NIFTY 50 market data using Meta-Heuristic Optimization (MHO). The system continuously monitors for concept drift and reoptimizes a temporal ensemble of XGBoost classifiers in real time using a council of three evolutionary algorithms.

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Data Pipeline](#data-pipeline)
4. [Ensemble Models](#ensemble-models)
5. [Drift Detection](#drift-detection)
6. [MHO Council](#mho-council)
7. [Live Prediction Scheduler](#live-prediction-scheduler)
8. [Web Dashboard & API](#web-dashboard--api)
9. [Chatbot](#chatbot)
10. [Firebase Data Model](#firebase-data-model)
11. [Configuration](#configuration)
12. [Project Structure](#project-structure)
13. [Running the System](#running-the-system)

---

## Overview

Finstream MetaOpt predicts the 5-day directional movement of the NIFTY 50 index (`^NSEI`). The target variable is binary: `1` if the close price 5 trading days later is higher than the current close, `0` otherwise.

The system is split into two modes:

| Mode | Description |
|---|---|
| **Simulation** | Runs the full adaptive vs. static comparison over historical test data (2020–present) |
| **Live** | Makes daily real-time predictions at 09:30 IST and evaluates resolved predictions at 09:35 IST |

---

## System Architecture

```
Yahoo Finance (yfinance)
        │
        ▼
┌───────────────────┐
│   Data Pipeline   │  download → feature engineering → target generation → train/test split
└────────┬──────────┘
         │  data/processed/train.csv  (2015–2019)
         │  data/processed/test.csv   (2020–present)
         ▼
┌───────────────────────────────────────┐
│        Temporal Ensemble              │
│  ┌──────────┐ ┌──────────┐ ┌───────┐ │
│  │Model_OLD │ │Model_MED │ │Model  │ │
│  │2015–2017 │ │2016–2018 │ │RECENT │ │
│  │(XGBoost) │ │(XGBoost) │ │2017–19│ │
│  └────┬─────┘ └────┬─────┘ └───┬───┘ │
│       └────────────┴───────────┘     │
│         weighted ensemble predict    │
└──────────────────┬────────────────────┘
                   │
         ┌─────────▼──────────┐
         │   ADWIN Drift      │  delta=0.2, continuous error |prob − truth|
         │   Detector         │
         └─────────┬──────────┘
                   │ drift detected
                   ▼
     ┌─────────────────────────────────┐
     │          MHO Council            │
     │  ┌───────┐ ┌──────┐ ┌───────┐  │
     │  │  PSO  │ │  GA  │ │  GWO  │  │
     │  └───┬───┘ └──┬───┘ └───┬───┘  │
     │      └────────┼─────────┘      │
     │    softmax-weighted aggregation │
     └─────────────────────────────────┘
                   │ updated weights & active features
                   ▼
         ┌─────────────────┐
         │    Firebase     │  Firestore (REST API)
         │    Firestore    │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │  Flask Dashboard│  + Chatbot (AWS Chalice + Amazon Bedrock)
         └─────────────────┘
```

---

## Data Pipeline

**Source:** NIFTY 50 index (`^NSEI`) via `yfinance`, starting from 2015-01-01.

**Modules:** `src/data_ingestion.py` → `src/feature_engineering.py` → `src/target_generation.py` → `src/dataset_splitting.py`

**Orchestrator:** `src/pipeline.py`

### Feature Engineering

Eight technical indicators are computed from daily OHLCV data:

| Feature | Description |
|---|---|
| `RSI_14` | Relative Strength Index, 14-day window |
| `MACD` | MACD line (12/26 EMA) |
| `MACD_Signal` | 9-day EMA of MACD |
| `MACD_Diff` | MACD histogram (MACD − Signal) |
| `BB_Position` | Bollinger Band %B (20-day, 2σ) |
| `MA_5_20_Ratio` | 5-day MA / 20-day MA |
| `Volume_Change_Pct` | Daily volume change %, clipped to ±200% |
| `Yesterday_Return` | Previous day's close-to-close return (shifted by 1) |

**Library:** `ta` (Technical Analysis library for Python)

### Target Generation

```
Target = 1  if Close[t+5] > Close[t]
Target = 0  otherwise
```

The last 5 rows of any dataset are assigned `NaN` (no 5-day forward close available) and are dropped during cleaning.

### Dataset Splits

| Split | Date Range | Purpose |
|---|---|---|
| Train | 2015-01-01 – 2019-12-31 | Model training windows |
| Test | 2020-01-01 – present | Simulation and live evaluation |
| Baseline Evaluation | 2020-01-01 – 2020-12-31 | Static model evaluation subset |

Splits are saved as CSV to `data/processed/`. The 2020 COVID crash is intentionally included in the test set to exercise drift detection.

---

## Ensemble Models

**Module:** `src/02_train_models.py`

Three XGBoost classifiers are trained on overlapping temporal windows, each representing a different market regime:

| Model | Training Window |
|---|---|
| `Model_OLD` | 2015-01-01 – 2017-12-31 |
| `Model_MEDIUM` | 2016-01-01 – 2018-12-31 |
| `Model_RECENT` | 2017-01-01 – 2019-12-31 |

### Training Protocol

- Each window uses a strict **chronological 80/20 train/validation split** (no shuffle, split by sorted date index).
- Validation set is used only for Brier Score and F1 evaluation; it does not influence training.
- `inf`/`-inf` values are replaced with `NaN` before training (XGBoost native NaN handling).

### XGBoost Hyperparameters (identical across all three models)

| Parameter | Value |
|---|---|
| `max_depth` | 3 |
| `learning_rate` | 0.03 |
| `n_estimators` | 1000 |
| `subsample` | 0.7 |
| `colsample_bytree` | 0.7 |
| `min_child_weight` | 3 |
| `gamma` | 1 |
| `reg_alpha` (L1) | 0.1 |
| `reg_lambda` (L2) | 1.0 |
| `eval_metric` | logloss |
| `random_state` | 42 |

### Evaluation Metric

**Brier-based score** is used throughout: `score = 1 − mean((prob − truth)²)`. This is the complement of the standard Brier Score, so higher is better.

### Model Artifacts

Trained models are serialized with `joblib` to:
- `models/model_old.pkl`
- `models/model_medium.pkl`
- `models/model_recent.pkl`

Training metadata (model name, training period, Brier score, F1) is written to the `model_registry` Firestore collection.

---

## Drift Detection

**Module:** `src/03_stream_loop.py`

Concept drift is detected using the **ADWIN** (Adaptive Windowing) algorithm from the `river` library.

| Parameter | Value | Rationale |
|---|---|---|
| `delta` | 0.2 | High sensitivity — detects drift early to stay ahead of performance decay |
| Input signal | `\|prob − truth\|` (continuous error) | Lower variance than binary error; faster detection |
| Min window for MHO | 120 resolved predictions | Wider window provides more data for optimizer evaluation |

### Prediction Buffer

A 5-step prediction buffer is maintained. Each prediction resolves 5 trading days after it is made, matching the 5-day prediction horizon. When a prediction resolves, its continuous error is fed to ADWIN.

### Design Decision: Continuous Error over Binary Error

Binary error (0/1) was not used as the ADWIN input because it has higher variance, which slows down detection. Using `|prob − truth|` provides a finer-grained, lower-variance signal that triggers faster reoptimization.

---

## MHO Council

**Module:** `src/05_mho_council.py`

When drift is detected, the `MHOCouncil` runs three independent meta-heuristic algorithms in sequence and combines their solutions into a single optimized configuration for the ensemble.

### Search Space

An 11-dimensional continuous vector `[0, 1]`:

| Dimensions | Meaning |
|---|---|
| 0 – 7 | Feature flags — value > 0.5 means the feature is active |
| 8 – 10 | Ensemble weights for `[Model_OLD, Model_MEDIUM, Model_RECENT]` |

Ensemble weight genes are always normalized to sum to 1 after every update operation.

### Fitness Function

```
fitness = 1 − mean((ensemble_prob − truth)²)
```

Where `ensemble_prob = w_old·p_old + w_medium·p_medium + w_recent·p_recent`. Model probabilities are precomputed once per council call for efficiency.

### Algorithms

#### Particle Swarm Optimization (PSO)

| Parameter | Value |
|---|---|
| Particles | 20 |
| Iterations | 30 |
| Inertia weight (`w`) | 0.7 |
| Cognitive parameter (`c1`) | 1.5 |
| Social parameter (`c2`) | 1.5 |

Particles are clipped to `[0, 1]` after each velocity update. Weight genes (dims 8–10) are renormalized to sum to 1 after each position update.

#### Genetic Algorithm (GA)

| Parameter | Value |
|---|---|
| Population size | 20 |
| Generations | 30 |
| Crossover rate | 0.8 |
| Mutation rate | 0.1 per gene |
| Mutation std | 0.05 (Gaussian) |
| Selection | Tournament (size 3) |
| Crossover | Uniform |
| Elitism | Top 2 preserved |

Offspring are clipped to `[0, 1]` and weight genes are renormalized after mutation.

#### Grey Wolf Optimizer (GWO)

| Parameter | Value |
|---|---|
| Wolves | 20 |
| Iterations | 30 |

Uses the standard alpha-beta-delta leadership hierarchy. The encircling parameter `a` decreases linearly from 2 to 0 over iterations. Omega wolves (all wolves except alpha, beta, delta) update their positions toward all three leaders and are renormalized after each update.

### Council Aggregation

The three algorithm solutions are combined using a **softmax-weighted linear combination**:

```
final_solution = cw_pso · sol_pso + cw_ga · sol_ga + cw_gwo · sol_gwo
```

Council weights are initialized equally at `[1/3, 1/3, 1/3]` and updated after each drift event using softmax over the algorithm fitness scores:

```python
exp_fit = exp(fitnesses - max(fitnesses))  # numerical stability
council_weights = exp_fit / sum(exp_fit)
```

**Weight update guard:** Council weights are only updated if the spread between the best and worst algorithm fitness is ≥ 0.01. Below this threshold, the fitness values are too close to extract a meaningful signal, so existing weights are preserved.

### Post-Optimization Constraints

1. **No-Worse-Than-Static guard:** If the optimized solution's fitness does not exceed the current solution's fitness by more than 0.001, the weight update is suppressed and the current configuration is retained.
2. **Minimum feature constraint:** At least 3 features must be active. If fewer than 3 feature flags exceed 0.5 after optimization, the top-3 flags by value are forced to 0.51.

### Council Lifecycle

The `MHOCouncil` instance is created once at the start of each simulation run and persists across all drift events. Council weights accumulate learning from successive drift events within a run.

---

## Live Prediction Scheduler

**Module:** `src/07_scheduler.py`

The scheduler runs two jobs daily for NIFTY 50 trading days (weekends are automatically skipped):

| Job | Time (IST) | Description |
|---|---|---|
| `daily_predict` | 09:30 | Fetches the latest 60 days of NIFTY data, engineers features, makes an ensemble prediction, saves to Firebase |
| `daily_evaluate` | 09:35 | Evaluates the prediction made 5 business days ago against the actual close price, updates ADWIN, triggers council if drift is detected |

**Scheduler library:** APScheduler (`BlockingScheduler`)

**Timezone:** Asia/Kolkata (IST)

### State Persistence

System state (active features, ensemble weights, council weights) is persisted in Firestore under `system/current`. On startup, `initialize_system()` restores this state. This allows the live system to survive restarts without losing learned configurations.

A guard flag (`_system_initialized`) prevents re-initialization when the scheduler module is re-imported from Flask.

### Feature Engineering (Live)

Live feature engineering re-implements the same 8 indicators directly using the `ta` library on the last 60 days of yfinance data. Only the most recent row is used for prediction. Volume change is clipped to ±200% and the last 5 rows are used as a warmup buffer before the computation stabilizes.

---

## Web Dashboard & API

**Module:** `src/app.py`

**Framework:** Flask, served via Gunicorn with a 300-second timeout (`Procfile`).

### REST Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | Dashboard | Renders the HTML dashboard |
| `GET /api/summary` | Public | Latest simulation summary (Brier scores, drift count) |
| `GET /api/config` | Public | Static system configuration metadata |
| `GET /api/simulation` | Public | All adaptive and static simulation results |
| `GET /api/simulation_drift` | Public | All simulation drift events |
| `GET /api/model_registry` | Public | Trained model metadata |
| `GET /api/live/state` | Public | Current live model state from Firestore |
| `GET /api/live/predictions` | Public | 20 most recent live predictions |
| `GET /api/live/drift` | Public | 10 most recent live drift events |
| `GET /api/live/evaluations` | Public | 30 most recent evaluation records |
| `GET /api/diagnostics` | Public | Firestore connectivity check |
| `GET /health` | Public | Health check |
| `POST /run/predict` | Cron-authenticated | Triggers `daily_predict` in a background thread |
| `POST /run/evaluate` | Cron-authenticated | Triggers `daily_evaluate` in a background thread |
| `POST /run/evaluate_pending` | Cron-authenticated | Triggers evaluation of last N unresolved predictions |
| `GET /api/job_status` | Public | Polls the status of a background job (`?job=predict` or `?job=evaluate`) |

### Cron Authentication

Cron-triggered endpoints require an `X-Cron-Token` header matching the `CRON_SECRET` environment variable. Requests without a valid token return HTTP 401.

### Background Jobs

Long-running jobs (predict, evaluate) are executed in daemon threads via `threading.Thread`. The HTTP response returns immediately with HTTP 202 and the job result is accessible via `/api/job_status`.

### Frontend

Static assets are served from `static/`. JavaScript API calls use relative `/api/...` paths (no hard-coded hostnames). The main dashboard is a single-page application rendered from `templates/dashboard.html`.

---

## Chatbot

**Directory:** `chatbot/`

**Framework:** AWS Chalice (serverless AWS Lambda deployment)

**Model:** Meta Llama 4 Maverick 17B Instruct (`us.meta.llama4-maverick-17b-instruct-v1:0`) via Amazon Bedrock

**Agent framework:** Strands (with `AgentSkills` plugin)

The chatbot exposes two endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | Health check | Returns `{"status": "ok"}` |
| `POST /chat` | Chat | Accepts `{"message": "...", "history": [...]}` and returns `{"response": "..."}` |

The agent has two tools:
1. `firebase_context` — fetches live data (predictions, evaluations, drift events, model state) from Firestore
2. `finstream-context` skill — provides knowledge about the system architecture (loaded via `AgentSkills` plugin from `chalicelib/skills/finstream-context`)

The system prompt instructs the agent to always call `firebase_context` first for any live data question and to never fabricate live values. Responses must be plain English with no code blocks.

---

## Firebase Data Model

All data is stored in **Google Cloud Firestore** via the REST API (no service account or Firebase Admin SDK required — uses the public Firestore REST API with an API key).

| Collection | Document ID | Contents |
|---|---|---|
| `predictions` | `YYYY-MM-DD` | Date, prediction (0/1), label, probability, ensemble weights, active features, resolved flag, truth, error |
| `evaluations` | `YYYY-MM-DD` | Date, prediction, truth, error, continuous error, drift flag |
| `drift_events` | `YYYY-MM-DD_rowindex` | Before/after weights, before/after features, algorithm fitnesses, council weights |
| `system/current` | `current` | Active features, ensemble weights, council weights, drift count, last prediction date |
| `model_registry` | `model_old` / `model_medium` / `model_recent` | Model name, training period, Brier score, F1 score, trained-at timestamp |
| `simulation_results` | `YYYY-MM-DD` (adaptive) / `static_YYYY-MM-DD` (static) | Full per-step simulation log for both adaptive and static runs |
| `simulation_drift_events` | `YYYY-MM-DD_rowindex` | Simulation drift event log |
| `simulation_summary` | `latest` | Aggregated simulation metrics |

---

## Configuration

All runtime configuration is loaded from environment variables via `python-dotenv` (`.env` file). See `.env.example` for the full list.

| Variable | Default | Description |
|---|---|---|
| `FIREBASE_PROJECT_ID` | `mlmodeldriftusingmho` | Firestore project ID |
| `FIREBASE_API_KEY` | — | Firestore REST API key |
| `CRON_SECRET` | — | Token required for cron-triggered HTTP endpoints |
| `NIFTY_TICKER` | `^NSEI` | Yahoo Finance ticker symbol |
| `PREDICTION_HORIZON` | `5` | Number of trading days into the future for the target |
| `ADWIN_DELTA` | `1.0` | ADWIN sensitivity for the live scheduler (note: simulation uses 0.2 hardcoded) |
| `MODEL_DIR` | `models` | Directory containing serialized model `.pkl` files |
| `DATA_DIR` | `data/processed` | Directory containing processed CSV datasets |

---

## Project Structure

```
finstream-metaopt/
├── src/
│   ├── pipeline.py              # Data pipeline orchestrator
│   ├── data_ingestion.py        # yfinance NIFTY 50 downloader
│   ├── feature_engineering.py   # Technical indicator computation
│   ├── target_generation.py     # 5-day forward return binary target
│   ├── dataset_splitting.py     # Chronological train/test/eval splits
│   ├── 02_train_models.py       # Temporal window model training
│   ├── 03_stream_loop.py        # Simulation stream loop with ADWIN + MHO
│   ├── 05_mho_council.py        # PSO, GA, GWO + council aggregation
│   ├── 07_scheduler.py          # Daily prediction and evaluation jobs
│   ├── firebase_client.py       # Firestore REST API wrapper
│   ├── yfinance_session.py      # yfinance retry session wrapper
│   └── app.py                   # Flask dashboard and API
├── chatbot/
│   ├── app.py                   # AWS Chalice chatbot (Bedrock + Strands)
│   └── chalicelib/
│       └── tools/context.py     # firebase_context tool for the agent
├── models/
│   ├── model_old.pkl
│   ├── model_medium.pkl
│   └── model_recent.pkl
├── data/processed/              # Generated CSVs (not committed)
├── static/                      # Frontend assets
├── templates/                   # Jinja2 HTML templates
├── Procfile                     # Gunicorn entry point
├── requirements.txt
├── pyproject.toml               # Python 3.13+ project metadata
└── .env.example
```

> **Note:** Numeric prefixes on source modules (e.g., `02_train_models.py`, `03_stream_loop.py`) prevent direct import with standard Python syntax. These modules are imported at runtime using `importlib.import_module`.

---

## Running the System

### Prerequisites

- Python 3.13+
- Firebase project with Firestore enabled
- Environment variables configured (see `.env.example`)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Data Pipeline

```bash
python -m src.pipeline
```

### Train Ensemble Models

```bash
python -m src.02_train_models
```

### Run Historical Simulation

```bash
python -m src.03_stream_loop
```

### Run the Web Server

```bash
gunicorn src.app:app --timeout 300
```

### Run the Scheduler (Local Test Mode)

```bash
python src/07_scheduler.py --test
```

### Deploy the Chatbot

The chatbot is deployed as an AWS Lambda function using the Chalice CLI from the `chatbot/` directory.
