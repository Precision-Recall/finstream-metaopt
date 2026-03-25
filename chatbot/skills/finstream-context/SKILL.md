---
name: finstream-context
description: >
  Load this context when the user asks about predictions, evaluations,
  drift events, model state, system performance, feature selection,
  ensemble weights, or anything related to the finstream-metaopt
  NIFTY50 adaptive ML system. Also load when the user asks questions
  like 'how is the system doing', 'what happened today', 'was drift
  detected', 'what are the current weights'. Do NOT load for general
  ML theory questions, unrelated coding tasks, or questions answerable
  from training knowledge alone.
version: "1.0"
requires_tool: firebase_context
collections:
  - predictions
  - evaluations
  - drift_events
  - system/current
  - simulation_summary
---

# Section 1 — What This System Is
Finstream-metaopt is a live adaptive ML pipeline designed to predict NIFTY50 5-day forward returns. The system features autonomous concept drift detection and a Meta-Heuristic Optimization (MHO) Council for model adaptation. It is implemented as a Flask monolith deployed on Render, using Firebase Firestore as its primary data store. Execution is triggered via GitHub Actions on a daily cron schedule.

# Section 2 — The Daily Loop
The system operates on a Two-Stage Daily Loop:
- **09:30 IST: daily_predict**
    - Fetch 60 days of historical data via yfinance
    - Engineer 8 technical features
    - Generate ensemble prediction using active models/weights
    - Save prediction and `close_at_prediction` to Firebase
- **09:50 IST: daily_evaluate**
    - Read `close_at_prediction` from Firebase (minimizes API calls)
    - Fetch current day's close price (single yfinance call)
    - Compute ground truth label
    - Update ADWIN drift detector with error signal
    - **IF DRIFT DETECTED**:
        - Reconstruct last 60 resolved rows
        - Run MHO Council (PSO, GA, GWO)
        - Update active features and ensemble weights
        - Reset ADWIN

# Section 3 — The Three Models
| Model Name | Training Window | What It Captures |
| :--- | :--- | :--- |
| Model_OLD | 2015–2017 | Long-term historical regimes |
| Model_MEDIUM | 2016–2018 | Intermediate transitional patterns |
| Model_RECENT | 2017–2019 | Recent volatility and trends |
*Note: Models are pre-trained and fixed. The system adapts by changing ensemble weights and feature selection.*

# Section 4 — The 8 Features
1. **RSI_14**: Relative Strength Index (Momentum)
2. **MACD**: Moving Average Convergence Divergence
3. **MACD_Signal**: Signal line for MACD
4. **MACD_Diff**: Difference between MACD and Signal
5. **BB_Position**: Price position relative to Bollinger Bands
6. **MA_5_20_Ratio**: Ratio of 5-day to 20-day Moving Average
7. **Volume_Change_Pct**: Daily percentage change in volume
8. **Yesterday_Return**: Previous day's price return
*Implementation Note: Deselected features are zeroed out but kept in the input vector to maintain XGBoost shape.*

# Section 5 — Drift Detection
The system uses the **ADWIN (Adaptive Windowing)** algorithm. Unlike traditional accuracy monitoring, it tracks a continuous error signal: `|predicted_probability - truth|`. This allows the system to detect subtle shifts in model confidence before they manifest as outright misclassifications. When the average error significantly deviates, a drift event is triggered.

# Section 6 — MHO Council
The MHO Council optimizes an 11-dimensional search space (8 feature flags + 3 ensemble weights). 
- **Algorithms**: Particle Swarm Optimization (PSO), Genetic Algorithm (GA), and Grey Wolf Optimizer (GWO).
- **Aggregation**: A softmax-weighted council approach combines the best results from all three.
- **Fitness Function**: `Brier Score (1 - MSE) - 0.01 * (active_features / 8)`.
- **Constraint**: Minimum of 3 active features must be maintained.

# Section 7 — Firebase Collections
| Collection | Document ID pattern | Contents |
| :--- | :--- | :--- |
| `predictions` | `YYYY-MM-DD` | `prediction_label`, `ensemble_probability`, `close_at_prediction`, `resolved`, `error` |
| `evaluations` | `YYYY-MM-DD` | `truth`, `error`, `drift_detected` |
| `drift_events` | date_rowindex | `active_features_before`, `active_features_after`, `w_old/medium/recent_before/after`, `fit_pso/ga/gwo`, `cw_pso/ga/gwo` |
| `system/current` | `current` (static) | Active features and current model weights |
| `simulation_summary`| `latest` (static) | Overall historical performance metrics |

# Section 8 — Known Constraints
- **Render Cold-Starts**: GitHub Actions performs a health-check loop to wake the service before jobs.
- **yfinance Rate Limiting**: Mitigated by `yf_fetch_with_retry` and logic that avoids redundant price fetches during evaluation.
- **Execution Timing**: 20-minute gap between predict (09:30) and evaluate (09:50) ensures stability.
- **Feature Reconstruction**: `daily_evaluate` currently uses a mock for historical feature reconstruction; real reconstruction is a planned upgrade.

# Section 9 — How the Chatbot Should Use This Context
- **Tool First**: Always call `firebase_context` tool before answering questions about live system state.
- **Configuration**: Use `system/current` to explain active features and ensemble weights.
- **Accuracy**: Use `predictions` (resolved flag and truth) to answer questions about recent performance.
- **Explain Drift**: Use `drift_events` to show exactly how model weights shifted after a detection.
- **Transparency**: If Firebase is unavailable, state it clearly. Do not hallucinate live data.
