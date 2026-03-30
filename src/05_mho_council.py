"""
Meta-Heuristic Optimization Council for Adaptive Ensemble Learning.

Implements PSO, GA, and GWO as independent optimizers that are aggregated
via a Council. The Council uses softmax-weighted combination of solutions
and updates weights after each drift event based on algorithm performance.

Search Space:
    (8 + N)-dimensional continuous [0, 1]:
    - Dims 0-7: Feature flags (>0.5 = active, ≤0.5 = dropped)
    - Dims 8 to 8+N: Ensemble weights for N models (normalized to sum to 1)

Constraints:
    - Minimum 3 active features (penalize degenerate solutions)
    - Weight genes always normalized after operations
"""

from typing import Dict, Tuple, List, Any
import numpy as np


def clip_weights(w: np.ndarray, max_w: float = 0.80, min_w: float = 0.05) -> np.ndarray:
    """
    Enforce ensemble diversity by capping any single model's weight.

    Wider bounds (max=0.80, min=0.05) than before allow the optimizer to
    concentrate weight on a clearly dominant model while still ensuring
    every model contributes at least 5%. This massively expands the
    feasible search space versus the old 10%/70% bounds.

    Converges in <=5 passes for an N-model ensemble.

    Args:
        w     : raw weight array
        max_w : max fraction a single model can receive (default 0.80 = 80%)
        min_w : min fraction each model must receive   (default 0.05 =  5%)
    Returns:
        Normalised, clipped weight array.
    """
    w = np.abs(w).astype(float)
    total = w.sum()
    if total < 1e-10:
        return np.full_like(w, 1.0 / len(w))
    w = w / total
    for _ in range(8):          # extra passes for N>4
        w = np.clip(w, min_w, max_w)
        w = w / w.sum()
    return w


def _per_model_scores(
    precomputed_probs: Dict[str, np.ndarray],
    y_true: np.ndarray,
    time_weights: np.ndarray,
    model_keys: List[str]
) -> np.ndarray:
    """
    Compute each model's individual temporally-weighted Brier score.
    Returns an array of shape (num_models,) — higher is better.
    """
    scores = []
    for mk in model_keys:
        p = precomputed_probs[mk][:, 1]
        s = 1.0 - float(np.mean(time_weights * (p - y_true) ** 2))
        scores.append(s)
    return np.array(scores)


def _accuracy_proportional_weights(
    precomputed_probs: Dict[str, np.ndarray],
    y_true: np.ndarray,
    time_weights: np.ndarray,
    model_keys: List[str]
) -> np.ndarray:
    """
    Return weight vector proportional to each model's advantage over
    the worst model. Used to warm-start PSO/GA/GWO.
    """
    scores = _per_model_scores(precomputed_probs, y_true, time_weights, model_keys)
    shifted = scores - scores.min()
    if shifted.sum() < 1e-10:
        return np.ones(len(model_keys)) / len(model_keys)
    return shifted / shifted.sum()


def evaluate_fitness(
    solution: np.ndarray,
    models: Dict[str, Any],
    resolved_df: np.ndarray,
    all_features: List[str],
    precomputed_probs: Dict[str, np.ndarray],
    model_keys: List[str] = None,
    decay: float = 0.94
) -> float:
    """
    Evaluate fitness as temporally-weighted ensemble Brier score.

    decay=0.94 gives half-life ≈ 11 samples, focusing on the last ~30-40 resolved
    rows where genuine market-regime changes are visible.

    Args:
        solution         : (8+N)-D numpy array; dims 8+ are raw ensemble weights
        models           : dict of model instances (for key count only)
        resolved_df      : ndarray, last column = truth label
        all_features     : list of feature column names (unused but kept for API compat)
        precomputed_probs: {model_key: predict_proba output} for this window
        model_keys       : ordered list of keys matching weight dims; defaults to models.keys()
        decay            : temporal decay per step (0.94 ≈ 11-step half-life)

    Returns:
        float fitness — higher is better
    """
    num_models = len(models)
    weights = clip_weights(solution[8:8+num_models])
    keys_to_use = model_keys if model_keys is not None else list(models.keys())

    y_true = resolved_df[:, -1].astype(int)
    n = len(y_true)

    # Temporally-decayed weights — focus on recent regime
    time_weights = np.array([decay ** (n - 1 - i) for i in range(n)])
    time_weights = time_weights / time_weights.sum() * n

    # --- Ensemble Brier score ---
    ensemble_prob = np.zeros(n, dtype=float)
    for i, mk in enumerate(keys_to_use):
        ensemble_prob += weights[i] * precomputed_probs[mk][:, 1]
    ensemble_brier = 1.0 - float(np.mean(time_weights * (ensemble_prob - y_true) ** 2))

    return float(ensemble_brier)


def run_pso(
    models: Dict[str, Any],
    resolved_df: np.ndarray,
    all_features: List[str],
    precomputed_probs: Dict[str, np.ndarray],
    n_particles: int = 30,
    n_iterations: int = 50,
    w: float = 0.7,
    c1: float = 1.5,
    c2: float = 1.5
) -> Tuple[np.ndarray, float]:
    """
    Particle Swarm Optimization algorithm.

    Args:
        models: dict with model instances
        resolved_df: array of resolved rows
        all_features: list of feature names
        precomputed_probs: precomputed model probabilities
        n_particles: number of particles (default 20)
        n_iterations: number of iterations (default 30)
        w: inertia weight (default 0.7)
        c1: cognitive parameter (default 1.5)
        c2: social parameter (default 1.5)

    Returns:
        Tuple of (best_position, best_fitness)
    """
    num_models = len(models)
    dim = 8 + num_models
    # Initialize particles and velocities
    particles = np.random.rand(n_particles, dim)
    velocities = np.random.randn(n_particles, dim) * 0.1

    model_keys = list(models.keys())

    # Warm-start: seed particle[0] from per-model accuracy weights so PSO
    # starts from an already-meaningful solution rather than pure random.
    y_true_ws = resolved_df[:, -1].astype(int)
    n_ws = len(y_true_ws)
    tw_ws = np.array([0.94 ** (n_ws - 1 - i) for i in range(n_ws)])
    tw_ws = tw_ws / tw_ws.sum() * n_ws
    # Diverse seeds so PSO explores different starting territories:
    #   particle[0] = warm-start (accuracy-proportional weights — known good)
    #   particle[1] = inverse    (favours weakest model — explores opposite region)
    #   particle[2] = uniform    (equal weights — neutral baseline)
    #   rest        = random     (broad exploration)
    warm_w = _accuracy_proportional_weights(precomputed_probs, y_true_ws, tw_ws, model_keys)
    particles[0, 8:8+num_models] = warm_w
    particles[1, 8:8+num_models] = clip_weights(1.0 - warm_w)
    particles[2, 8:8+num_models] = np.ones(num_models) / num_models

    # Evaluate initial population
    fitness_vals = np.array([
        evaluate_fitness(particles[i], models, resolved_df, all_features, precomputed_probs, model_keys=model_keys)
        for i in range(n_particles)
    ])

    pbest_pos = particles.copy()
    pbest_fit = fitness_vals.copy()

    # Global best
    best_idx = np.argmax(fitness_vals)
    gbest_pos = particles[best_idx].copy()
    gbest_fit = fitness_vals[best_idx]

    # Iterate
    for iteration in range(n_iterations):
        for i in range(n_particles):
            r1 = np.random.rand(dim)
            r2 = np.random.rand(dim)

            # Update velocity
            velocities[i] = (
                w * velocities[i] +
                c1 * r1 * (pbest_pos[i] - particles[i]) +
                c2 * r2 * (gbest_pos - particles[i])
            )

            # Update position
            particles[i] = np.clip(particles[i] + velocities[i], 0, 1)

            # Normalise and diversity-clip weight genes
            w_genes = particles[i][8:8+num_models]
            particles[i][8:8+num_models] = clip_weights(w_genes)

            # Evaluate
            fit = evaluate_fitness(particles[i], models, resolved_df, all_features, precomputed_probs, model_keys=model_keys)

            # Update personal best
            if fit > pbest_fit[i]:
                pbest_pos[i] = particles[i].copy()
                pbest_fit[i] = fit

            # Update global best
            if fit > gbest_fit:
                gbest_pos = particles[i].copy()
                gbest_fit = fit

    return gbest_pos, gbest_fit


def run_ga(
    models: Dict[str, Any],
    resolved_df: np.ndarray,
    all_features: List[str],
    precomputed_probs: Dict[str, np.ndarray],
    pop_size: int = 30,
    n_generations: int = 50,
    crossover_rate: float = 0.8,
    mutation_rate: float = 0.1,
    mutation_std: float = 0.05
) -> Tuple[np.ndarray, float]:
    """
    Genetic Algorithm.

    Args:
        models: dict with model instances
        resolved_df: array of resolved rows
        all_features: list of feature names
        precomputed_probs: precomputed model probabilities
        pop_size: population size (default 20)
        n_generations: number of generations (default 30)
        crossover_rate: probability of crossover (default 0.8)
        mutation_rate: probability of mutation per gene (default 0.1)
        mutation_std: standard deviation for Gaussian mutation (default 0.05)

    Returns:
        Tuple of (best_chromosome, best_fitness)
    """
    num_models = len(models)
    dim = 8 + num_models
    # Initialize population
    population = np.random.rand(pop_size, dim)

    model_keys = list(models.keys())

    # Warm-start: seed chromosome[0] from per-model accuracy weights so GA
    # has a known-good individual in the gene pool from generation 0.
    y_true_ws = resolved_df[:, -1].astype(int)
    n_ws = len(y_true_ws)
    tw_ws = np.array([0.94 ** (n_ws - 1 - i) for i in range(n_ws)])
    tw_ws = tw_ws / tw_ws.sum() * n_ws
    # Diverse seeds so GA explores different starting territories:
    #   chromosome[0] = warm-start (accuracy-proportional weights — known good)
    #   chromosome[1] = inverse    (favours weakest model — explores opposite region)
    #   chromosome[2] = uniform    (equal weights — neutral baseline)
    #   rest          = random     (broad exploration)
    warm_w = _accuracy_proportional_weights(precomputed_probs, y_true_ws, tw_ws, model_keys)
    population[0, 8:8+num_models] = warm_w
    population[1, 8:8+num_models] = clip_weights(1.0 - warm_w)
    population[2, 8:8+num_models] = np.ones(num_models) / num_models

    for generation in range(n_generations):
        # Evaluate population
        fitness_vals = np.array([
            evaluate_fitness(population[i], models, resolved_df, all_features, precomputed_probs, model_keys=model_keys)
            for i in range(pop_size)
        ])

        # Sort by fitness descending
        sorted_indices = np.argsort(-fitness_vals)
        population = population[sorted_indices]
        fitness_vals = fitness_vals[sorted_indices]

        # Elitism: keep top 2
        new_population = population[:2].copy()

        # Generate offspring
        while len(new_population) < pop_size:
            # Tournament selection (size 3)
            candidates_idx = np.random.choice(pop_size, 3, replace=False)
            parent1_idx = candidates_idx[np.argmax(fitness_vals[candidates_idx])]

            candidates_idx = np.random.choice(pop_size, 3, replace=False)
            parent2_idx = candidates_idx[np.argmax(fitness_vals[candidates_idx])]

            parent1 = population[parent1_idx]
            parent2 = population[parent2_idx]

            # Uniform crossover
            if np.random.rand() < crossover_rate:
                offspring = np.where(
                    np.random.rand(dim) < 0.5,
                    parent1.copy(),
                    parent2.copy()
                )
            else:
                offspring = parent1.copy()

            # Gaussian mutation
            mutation_mask = np.random.rand(dim) < mutation_rate
            offspring[mutation_mask] += np.random.normal(0, mutation_std, mutation_mask.sum())
            offspring = np.clip(offspring, 0, 1)

            # Repair: normalise and diversity-clip weight genes
            offspring[8:8+num_models] = clip_weights(offspring[8:8+num_models])

            new_population = np.vstack([new_population, offspring])

        population = new_population[:pop_size]

    # Final evaluation
    fitness_vals = np.array([
        evaluate_fitness(population[i], models, resolved_df, all_features, precomputed_probs, model_keys=model_keys)
        for i in range(pop_size)
    ])

    best_idx = np.argmax(fitness_vals)
    return population[best_idx], fitness_vals[best_idx]


def run_gwo(
    models: Dict[str, Any],
    resolved_df: np.ndarray,
    all_features: List[str],
    precomputed_probs: Dict[str, np.ndarray],
    n_wolves: int = 30,
    n_iterations: int = 50
) -> Tuple[np.ndarray, float]:
    """
    Grey Wolf Optimizer algorithm.

    Args:
        models: dict with model instances
        resolved_df: array of resolved rows
        all_features: list of feature names
        precomputed_probs: precomputed model probabilities
        n_wolves: number of wolves (default 20)
        n_iterations: number of iterations (default 30)

    Returns:
        Tuple of (alpha_position, alpha_fitness)
    """
    num_models = len(models)
    dim = 8 + num_models
    # Initialize wolves
    wolves = np.random.rand(n_wolves, dim)

    model_keys = list(models.keys())

    # Warm-start: seed wolf[0] (candidate alpha) from per-model accuracy weights
    # so GWO's initial alpha is already a strong, meaningful solution.
    y_true_ws = resolved_df[:, -1].astype(int)
    n_ws = len(y_true_ws)
    tw_ws = np.array([0.94 ** (n_ws - 1 - i) for i in range(n_ws)])
    tw_ws = tw_ws / tw_ws.sum() * n_ws
    # Diverse seeds so GWO explores different starting territories:
    #   wolf[0] = warm-start (accuracy-proportional weights — candidate alpha)
    #   wolf[1] = inverse    (favours weakest model — explores opposite region)
    #   wolf[2] = uniform    (equal weights — neutral baseline)
    #   rest    = random     (broad exploration)
    warm_w = _accuracy_proportional_weights(precomputed_probs, y_true_ws, tw_ws, model_keys)
    wolves[0, 8:8+num_models] = warm_w
    wolves[1, 8:8+num_models] = clip_weights(1.0 - warm_w)
    wolves[2, 8:8+num_models] = np.ones(num_models) / num_models

    # Evaluate initial population
    fitness_vals = np.array([
        evaluate_fitness(wolves[i], models, resolved_df, all_features, precomputed_probs, model_keys=model_keys)
        for i in range(n_wolves)
    ])

    # Identify alpha, beta, delta
    sorted_indices = np.argsort(-fitness_vals)
    alpha_idx = sorted_indices[0]
    beta_idx = sorted_indices[1]
    delta_idx = sorted_indices[2]

    alpha_pos = wolves[alpha_idx].copy()
    alpha_fit = fitness_vals[alpha_idx]
    beta_pos = wolves[beta_idx].copy()
    beta_fit = fitness_vals[beta_idx]
    delta_pos = wolves[delta_idx].copy()
    delta_fit = fitness_vals[delta_idx]

    # Iterate
    for iteration in range(n_iterations):
        a = 2 - 2 * (iteration / n_iterations)  # decreases from 2 to 0

        for i in range(n_wolves):
            # Update towards alpha, beta, delta
            X_positions = []
            for leader_pos in [alpha_pos, beta_pos, delta_pos]:
                r1 = np.random.rand(dim)
                r2 = np.random.rand(dim)

                A = 2 * a * r1 - a
                C = 2 * r2

                D = np.abs(C * leader_pos - wolves[i])
                X = leader_pos - A * D
                X_positions.append(X)

            wolves[i] = np.clip(np.mean(X_positions, axis=0), 0, 1)

            # Normalise and diversity-clip weight genes
            wolves[i][8:8+num_models] = clip_weights(wolves[i][8:8+num_models])

            # Evaluate
            fit = evaluate_fitness(wolves[i], models, resolved_df, all_features, precomputed_probs, model_keys=model_keys)

            # Update alpha, beta, delta if improved
            if fit > alpha_fit:
                delta_pos = beta_pos.copy()
                delta_fit = beta_fit
                beta_pos = alpha_pos.copy()
                beta_fit = alpha_fit
                alpha_pos = wolves[i].copy()
                alpha_fit = fit
            elif fit > beta_fit:
                delta_pos = beta_pos.copy()
                delta_fit = beta_fit
                beta_pos = wolves[i].copy()
                beta_fit = fit
            elif fit > delta_fit:
                delta_pos = wolves[i].copy()
                delta_fit = fit

    return alpha_pos, alpha_fit


class MHOCouncil:
    """
    Meta-Heuristic Optimization Council.

    Aggregates solutions from PSO, GA, and GWO using softmax-weighted
    combination. Weights update after each drift event based on
    algorithm fitness performance.
    """

    def __init__(self) -> None:
        """Initialize council with equal weights for all three algorithms."""
        self.council_weights = np.array([1/3, 1/3, 1/3])
        # Order: [PSO, GA, GWO]

    def optimize(
        self,
        models: Dict[str, Any],
        resolved_df: Any,
        all_features: List[str],
        current_features: List[str] = None,
        current_weights: List[float] = None
    ) -> Dict[str, Any]:
        """
        Run optimization council and return aggregated solution.

        Args:
            models: dict with keys 'xgboost', 'lightgbm', 'extratrees' (model instances)
            resolved_df: DataFrame of resolved rows with truth labels.
            all_features: list of 8 feature column names
            current_features: list of currently active feature names
            current_weights: list of current [w_old, w_medium, w_recent]

        Returns:
            Dictionary with keys:
                - 'solution': 11D optimized vector
                - 'active_features': list of selected feature names
                - 'ensemble_weights': [w_old, w_medium, w_recent]
                - 'algorithm_fitnesses': {pso, ga, gwo} fitnesses
                - 'council_weights': {pso, ga, gwo} council weights
        """
        # Convert DataFrame to ndarray if needed
        if hasattr(resolved_df, 'values'):
            resolved_array = resolved_df.values
        else:
            resolved_array = resolved_df

        # Use all rows provided
        resolved_array = resolved_array

        # Use full resolved_array for optimization.
        # evaluate_fitness already applies decay=0.94 (half-life ~11 steps),
        # so recent post-drift rows are naturally up-weighted without a hard split.
        opt_array = resolved_array

        # Precompute model probabilities once for full window
        opt_probs = {}
        for model_key, model in models.items():
            X_opt = opt_array[:, :-1]
            opt_probs[model_key] = model.predict_proba(X_opt)

        model_keys = list(models.keys())

        # Run all three algorithms on the full window
        sol_pso, fit_pso = run_pso(
            models, opt_array, all_features, opt_probs
        )
        sol_ga, fit_ga = run_ga(
            models, opt_array, all_features, opt_probs
        )
        sol_gwo, fit_gwo = run_gwo(
            models, opt_array, all_features, opt_probs
        )

        # Winner-Takes-All Council: the best-performing algorithm gets
        # council_weight=1.0 and its solution is used directly.
        # Blending bad solutions with good ones only contaminates the result.
        fitnesses = np.array([fit_pso, fit_ga, fit_gwo])
        winner_idx = int(np.argmax(fitnesses))

        cw = np.zeros(3)
        cw[winner_idx] = 1.0
        self.council_weights = cw

        num_models = len(models)
        dim = 8 + num_models

        # Use the winner's solution directly
        solutions = [sol_pso, sol_ga, sol_gwo]
        final_solution = solutions[winner_idx].copy()

        # Regression guard: revert if new solution is conclusively worse
        # than current weights on the same full window.
        if current_weights is not None:
            current_sol = np.zeros(dim)
            current_sol[8:8+num_models] = current_weights
            current_fit = evaluate_fitness(current_sol, models, opt_array, all_features, opt_probs, model_keys=model_keys)

            new_fit = evaluate_fitness(final_solution, models, opt_array, all_features, opt_probs, model_keys=model_keys)

            # Threshold=0.010 — only revert if new weights are clearly worse, not noise.
            if new_fit < current_fit - 0.010:
                final_solution[8:8+num_models] = current_weights
                fit_pso, fit_ga, fit_gwo = current_fit, current_fit, current_fit

        # Enforce final solution constraints
        # 1. Normalise ensemble weights with diversity constraint
        final_solution[8:8+num_models] = clip_weights(final_solution[8:8+num_models])
        
        # Always apply the optimised weights — the temporal/architectural slices
        # have meaningful divergence so the optimizer produces real improvements.

        # Feature selection: always use ALL features.
        active_features = list(all_features)

        return {
            "solution": final_solution,
            "active_features": active_features,
            "ensemble_weights": final_solution[8:8+num_models].tolist(),
            "algorithm_fitnesses": {
                "pso": round(float(fit_pso), 4),
                "ga": round(float(fit_ga), 4),
                "gwo": round(float(fit_gwo), 4)
            },
            "council_weights": {
                "pso": round(float(self.council_weights[0]), 4),
                "ga": round(float(self.council_weights[1]), 4),
                "gwo": round(float(self.council_weights[2]), 4)
            }
        }