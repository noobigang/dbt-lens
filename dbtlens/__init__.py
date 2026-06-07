"""dbt Lens - a free dbt project health auditor.

Modules:
    parser: Parse a dbt manifest.json into a normalized ProjectSnapshot.
    scorer: Compute a 0-100 health score with dimensional breakdown.
    dag_renderer: Build an interactive DAG colored by per-model health.
    card_generator: Render a 1200x630 share card PNG.
    famous_projects: Comparison data for known public dbt projects.
"""

__version__ = "0.1.0"
