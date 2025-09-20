#!/usr/bin/env python3
"""
Training script that emits a single scalar score.
Reads config.json and computes a toy score with some differentiable properties.
"""

import json
import math
import random
import pathlib

def main():
    # Read config
    config_path = pathlib.Path(__file__).parent / "config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)

    lr = config["lr"]
    gamma = config["gamma"]
    entropy_coef = config["entropy_coef"]

    # Toy scoring function with some realistic properties:
    # - Learning rate has an optimal point around 0.01
    # - Gamma should be high (close to 1.0) but not too high
    # - Entropy coefficient should be small but non-zero

    # Learning rate component (quadratic with optimum around 0.01)
    lr_score = 100 - 50000 * (lr - 0.01) ** 2

    # Gamma component (sigmoid-like, prefers values close to 0.99)
    gamma_score = 20 / (1 + math.exp(-20 * (gamma - 0.95)))

    # Entropy component (logarithmic reward for small positive values)
    if entropy_coef > 0:
        entropy_score = 5 * math.log(entropy_coef + 0.0001)
    else:
        entropy_score = -10

    # Base score
    base_score = lr_score + gamma_score + entropy_score

    # Add small random noise for realism (but keep it deterministic-ish)
    random.seed(42)  # Semi-deterministic
    noise = random.gauss(0, 0.2)

    final_score = base_score + noise

    # Emit exactly one JSON object to stdout
    result = {"score": final_score}
    print(json.dumps(result))

if __name__ == "__main__":
    main()