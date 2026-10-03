"""ML predictor and feature extraction for advisory prediction signals.

These are EXPERIMENT modules — the dispatcher works without them.
All predictions are advisory; they enrich DispatcherDecision.prediction_signals
but never override SLA rules, agent eligibility, or approval requirements.

Model artifacts are loaded from a configurable path (environment variable
or constructor argument).  Training happens OUTSIDE the runtime —
in research/platform/ml/ notebooks.
"""
