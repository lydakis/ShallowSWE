from __future__ import annotations


KAGGLE_DEFAULT_REGISTRATION_MODEL = "google/gemini-3-flash-preview"


def is_development_registration_probe(
    *,
    registration_requested: bool,
    plan_class: str | None,
    launch_model: str | None,
    observed_model: str,
) -> bool:
    """Return whether Kaggle is executing its zero-evidence task-registration probe."""
    return (
        registration_requested
        and plan_class == "development_shadow"
        and observed_model == KAGGLE_DEFAULT_REGISTRATION_MODEL
        and observed_model != launch_model
    )
