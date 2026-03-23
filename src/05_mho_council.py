"""
Meta-Heuristic Optimization Council for Adaptive Ensemble Learning.

Implements PSO, GA, and GWO as independent optimizers that are aggregated
via a Council. The Council uses softmax-weighted combination of solutions
and updates weights after each drift event based on algorithm performance.

Search Space:
    11-dimensional continuous [0, 1]:
    - Dims 0-7: Feature flags (>0.5 = active, ≤0.5 = dropped)
    - Dims 8-10: Ensemble weights (normalized to sum to 1)

Constraints:
    - Minimum 3 active features (penalize degenerate solutions)
    - Weight genes always normalized after operations
"""

from typing import Dict, Tuple, List, Any
import numpy as np


def evaluate_fitness(
    solution: np.ndarray,
    models: Dict[str, Any],
    resolved_df: np.ndarray,
    all_features: List[str],
    precomputed_probs: Dict[str, np.ndarray]
) -> float:
    """
    Evaluate fitness of a solution as ensemble Brier Score.

    Args:
        solution: 11D numpy array [feature_flags (0-7), weights (8-10)]
        models: dict with keys 'old', 'medium', 'recent' (not used directly,
                probabilities are precomputed)
        resolved_df: DataFrame of resolved rows with truth labels
        all_features: list of 8 feature column names
        precomputed_probs: dict with keys 'old', 'medium', 'recent',
                          each is (n_rows, 2) probability array

    Returns:
        Brier Score (0.0 penalty if <3 active features)
    """
    # Extract feature flags
    feature_flags = solution[:8]
    active_indices = np.where(feature_flags > 0.5)[0]

    # Constraint 1: Penalize degenerate solutions
    if len(active_indices) < 3:
        return 0.0

    # Extract and normalize ensemble weights
    weights = solution[8:11]
    weights = np.abs(weights) / np.abs(weights).sum()

    # Compute weighted ensemble probability
    # precomputed_probs each has shape (n_rows, 2)
    prob_old = precomputed_probs["old"][:, 1]      # prob of class 1
    prob_medium = precomputed_probs["medium"][:, 1]
    prob_recent = precomputed_probs["recent"][:, 1]

    ensemble_prob = (
        weights[0] * prob_old +
        weights[1] * prob_medium +
        weights[2] * prob_recent
    )
    predictions = (ensemble_prob > 0.5).astype(int)

    # Get true labels (last column of resolved_df)
    y_true = resolved_df[:, -1].astype(int)

    # Compute Brier-based score (1 - MSE)
    # This is a proper scoring rule that accounts for both accuracy and calibration
    brier_score = 1.0 - np.mean((ensemble_prob - y_true)**2)
    
    # Feature Parsimony (small penalty for more features to avoid overfitting)
    parsimony_penalty = 0.01 * (len(active_indices) / len(all_features))
    
    # Composite fitness: favor Brier Score with slight parsimony
    fitness = brier_score - parsimony_penalty
    return float(fitness)


def run_pso(
    models: Dict[str, Any],
    resolved_df: np.ndarray,
    all_features: List[str],
    precomputed_probs: Dict[str, np.ndarray],
    n_particles: int = 20,
    n_iterations: int = 30,
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
    # Initialize particles and velocities
    particles = np.random.rand(n_particles, 11)
    velocities = np.random.randn(n_particles, 11) * 0.1

    # Evaluate initial population
    fitness_vals = np.array([
        evaluate_fitness(particles[i], models, resolved_df, all_features, precomputed_probs)
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
            r1 = np.random.rand(11)
            r2 = np.random.rand(11)

            # Update velocity
            velocities[i] = (
                w * velocities[i] +
                c1 * r1 * (pbest_pos[i] - particles[i]) +
                c2 * r2 * (gbest_pos - particles[i])
            )

            # Update position
            particles[i] = np.clip(particles[i] + velocities[i], 0, 1)

            # Normalize weight genes (with safety check)
            w_sum = np.abs(particles[i][8:11]).sum()
            if w_sum > 1e-10:
                particles[i][8:11] = np.abs(particles[i][8:11]) / w_sum
            else:
                particles[i][8:11] = np.array([1/3, 1/3, 1/3])

            # Evaluate
            fit = evaluate_fitness(particles[i], models, resolved_df, all_features, precomputed_probs)

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
    pop_size: int = 20,
    n_generations: int = 30,
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
    # Initialize population
    population = np.random.rand(pop_size, 11)

    for generation in range(n_generations):
        # Evaluate population
        fitness_vals = np.array([
            evaluate_fitness(population[i], models, resolved_df, all_features, precomputed_probs)
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
                    np.random.rand(11) < 0.5,
                    parent1.copy(),
                    parent2.copy()
                )
            else:
                offspring = parent1.copy()

            # Gaussian mutation
            mutation_mask = np.random.rand(11) < mutation_rate
            offspring[mutation_mask] += np.random.normal(0, mutation_std, mutation_mask.sum())
            offspring = np.clip(offspring, 0, 1)

            # Repair: normalize weight genes (with safety check)
            w_sum = np.abs(offspring[8:11]).sum()
            if w_sum > 1e-10:
                offspring[8:11] = np.abs(offspring[8:11]) / w_sum
            else:
                offspring[8:11] = np.array([1/3, 1/3, 1/3])

            new_population = np.vstack([new_population, offspring])

        population = new_population[:pop_size]

    # Final evaluation
    fitness_vals = np.array([
        evaluate_fitness(population[i], models, resolved_df, all_features, precomputed_probs)
        for i in range(pop_size)
    ])

    best_idx = np.argmax(fitness_vals)
    return population[best_idx], fitness_vals[best_idx]


def run_gwo(
    models: Dict[str, Any],
    resolved_df: np.ndarray,
    all_features: List[str],
    precomputed_probs: Dict[str, np.ndarray],
    n_wolves: int = 20,
    n_iterations: int = 30
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
    # Initialize wolves
    wolves = np.random.rand(n_wolves, 11)

    # Evaluate initial population
    fitness_vals = np.array([
        evaluate_fitness(wolves[i], models, resolved_df, all_features, precomputed_probs)
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
            if i == alpha_idx or i == beta_idx or i == delta_idx:
                continue

            # Update towards alpha, beta, delta
            X_positions = []
            for leader_pos in [alpha_pos, beta_pos, delta_pos]:
                r1 = np.random.rand(11)
                r2 = np.random.rand(11)

                A = 2 * a * r1 - a
                C = 2 * r2

                D = np.abs(C * leader_pos - wolves[i])
                X = leader_pos - A * D
                X_positions.append(X)

            wolves[i] = np.clip(np.mean(X_positions, axis=0), 0, 1)

            # Normalize weight genes (with safety check)
            w_sum = np.abs(wolves[i][8:11]).sum()
            if w_sum > 1e-10:
                wolves[i][8:11] = np.abs(wolves[i][8:11]) / w_sum
            else:
                wolves[i][8:11] = np.array([1/3, 1/3, 1/3])

            # Evaluate
            fit = evaluate_fitness(wolves[i], models, resolved_df, all_features, precomputed_probs)

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
        all_features: List[str]
    ) -> Dict[str, Any]:
        """
        Run optimization council and return aggregated solution.

        Args:
            models: dict with keys 'old', 'medium', 'recent' (model instances)
            resolved_df: DataFrame of resolved rows with truth labels.
                        Uses last 60 rows if available, else all.
            all_features: list of 8 feature column names

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

        # Use last 60 rows for efficiency, or all if fewer available
        if len(resolved_array) > 60:
            resolved_array = resolved_array[-60:, :]
        else:
            resolved_array = resolved_array

        # Precompute model probabilities for all rows
        precomputed_probs = {}
        for model_key in ["old", "medium", "recent"]:
            model = models[model_key]
            # Extract feature columns (all but last column which is truth)
            X = resolved_array[:, :-1]
            probs = model.predict_proba(X)
            precomputed_probs[model_key] = probs

        # Run all three algorithms
        sol_pso, fit_pso = run_pso(
            models, resolved_array, all_features, precomputed_probs
        )
        sol_ga, fit_ga = run_ga(
            models, resolved_array, all_features, precomputed_probs
        )
        sol_gwo, fit_gwo = run_gwo(
            models, resolved_array, all_features, precomputed_probs
        )

        # Council aggregation: weighted combination
        solutions = np.array([sol_pso, sol_ga, sol_gwo])
        final_solution = (
            self.council_weights[0] * solutions[0] +
            self.council_weights[1] * solutions[1] +
            self.council_weights[2] * solutions[2]
        )

        # Update council weights using softmax of fitnesses
        fitnesses = np.array([fit_pso, fit_ga, fit_gwo])
        # Guard: only update if fitnesses have meaningful divergence
        # If all within 0.01 of each other, keep existing weights (no signal)
        if max(fitnesses) - min(fitnesses) >= 0.01:
            exp_fit = np.exp(fitnesses - fitnesses.max())  # numerical stability
            self.council_weights = exp_fit / exp_fit.sum()

        # Enforce final solution constraints
        # 1. Normalize ensemble weights
        w = final_solution[8:11]
        w_sum = np.abs(w).sum()
        if w_sum > 1e-10:
            final_solution[8:11] = np.abs(w) / w_sum
        else:
            final_solution[8:11] = np.array([1/3, 1/3, 1/3])

        # 2. Ensure minimum 3 active features
        flags = final_solution[:8]
        if (flags > 0.5).sum() < 3:
            top3_idx = np.argsort(flags)[-3:]
            flags[top3_idx] = 0.51
        final_solution[:8] = flags

        # Extract active features
        active_features = [
            all_features[i] for i in range(8)
            if final_solution[i] > 0.5
        ]

        return {
            "solution": final_solution,
            "active_features": active_features,
            "ensemble_weights": final_solution[8:11].tolist(),
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
