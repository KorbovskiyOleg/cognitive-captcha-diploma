"""CLI entry point for rendering feature-analysis visualizations."""

from __future__ import annotations

import argparse

from visualization.feature_visualizer import render_feature_visualizations


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Cognitive CAPTCHA feature visualization plots.")
    parser.add_argument("--target", default="top_right", help="Target name from config.CORNERS.")
    parser.add_argument("--output-dir", default="visualization/output", help="Directory for generated PNG files.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for HumanLikeEyeTracker demo data.")
    args = parser.parse_args()

    result = render_feature_visualizations(
        target_name=args.target,
        output_dir=args.output_dir,
        seed=args.seed,
    )

    print(f"Rendered feature visualizations for target={result.target_name!r}")
    for feature, path in result.image_paths.items():
        print(f"- {feature}: {path}")


if __name__ == "__main__":
    main()
