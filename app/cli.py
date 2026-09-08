"""Flask CLI commands."""
import click
from flask.cli import with_appcontext


@click.command("sync-listings")
@click.option(
    "--with-images/--no-images",
    default=True,
    show_default=True,
    help="Cache listing images during sync.",
)
@click.option(
    "--batch-size",
    type=int,
    default=None,
    help="Override SYNC_BATCH_SIZE (default from config).",
)
@with_appcontext
def sync_listings_cmd(with_images: bool, batch_size: int | None) -> None:
    """Fetch listings from API and upsert into the database (chunked)."""
    from app.services.sync_engine import sync_listings

    result = sync_listings(with_images=with_images, batch_size=batch_size)
    if result.get("status") == "SUCCESS":
        click.echo(
            f"Sync OK: processed={result.get('processed')} "
            f"sold={result.get('sold')} source={result.get('source')}"
        )
        return

    click.echo(f"Sync FAILED: {result.get('error')}", err=True)
    raise SystemExit(1)


@click.command("train-models")
@with_appcontext
def train_models_cmd() -> None:
    """Fit RF/hedonic locally and write instance/*.pkl for the web to serve."""
    from app.services.training import training_allowed
    from app.services.price_model import PriceModel
    from app.services.hedonic_model import HedonicModel

    if not training_allowed():
        click.echo("ENABLE_TRAINING=0 — refusing to train on a serve-only process.", err=True)
        raise SystemExit(1)
    rf = PriceModel().train()
    hedonic = HedonicModel().train()
    click.echo(f"train={rf} hedonic={hedonic}")
