# Hedonic analysis + isolated hedonic Docker — Design

**Date:** 2026-08-10  
**Status:** Approved (option 3 / 예)  
**agent.md:** venv/agent.md constitution applied to new stack only

## Goals

1. Introduce hedonic (헤도닉) price decomposition for auction hammer prices.
2. Surface attribute contributions + residuals in predict/forecast and weekly briefing.
3. Deploy on a **separate** Compose project (`wecarwpm_hedonic`, port **8091**) without touching `wecarwpm` `:8090`.
4. **Do not push to GitHub.**

## Hedonic model

- Target: `log(hammer_price)`
- Features: car_year, car_km (or km_bin ordinal), fuel, accident-free, imported, maker/model encodings (target/frequency or one-hot top-N), grade/gdetail hashed categories as needed
- Estimator: Ridge / ElasticNet on expanded features (interpretable coefficients); optional RF residual blender kept secondary
- Artifacts: `instance/hedonic_model.pkl` (+ metadata: feature names, r2, n_samples, trained_at)
- Train hook: same admin retrain / excel upload path as PriceModel
- Predict API: predicted price, contributions (만원), residual vs actual when available

## Briefing

- Keep ±5% + min samples filter
- Add hedonic residual score per trim when model available; badge/sort assist for large |residual|

## Docker (new only)

| Item | Value |
|------|-------|
| File | `docker-compose.hedonic.yml` |
| Project | `wecarwpm_hedonic` |
| Port | 8091:5000 |
| Dockerfile | `Dockerfile.hedonic` multi-stage python:3.12-slim-bookworm, non-root |
| Volume | `./instance-hedonic` |
| Leave alone | `docker-compose.yml`, running `wecarwpm` |

## Out of scope

- GitHub push
- Restart/rebuild of `:8090`
- Full rewrite of all SQLAlchemy call sites to 2.0 style
