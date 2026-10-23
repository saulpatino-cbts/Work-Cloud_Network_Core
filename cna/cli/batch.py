"""CLI: cna batch — offline export/import of discovery records (BUILD-03).

Commands:
  cna batch export  — package an engagement's discovery checkpoints into a
                      portable, offline batch record (topology only; no secrets)
  cna batch import  — merge a batch record into an online engagement, tying the
                      offline-scanned sources in as if discovered live
"""

from __future__ import annotations

import logging
from pathlib import Path

import click

from cna.core.batch_record import (
    BatchRecordError,
    export_batch_record,
    import_batch_record,
)
from cna.core.persistence import EngagementStore

logger = logging.getLogger("cna.cli.batch")


@click.group("batch")
def batch_group():
    """Export/import offline discovery records between appliances."""
    pass


@batch_group.command("export")
@click.option("--engagement-id", required=True, help="Engagement ID to export from")
@click.option("--out", "out_path", required=True, type=click.Path(), help="Output record file")
@click.option("--source-id", "source_ids", multiple=True,
              help="Only export these subscription/account IDs (repeatable; default: all)")
@click.option("--label", default="", help="Human label (customer/engagement name — not a secret)")
@click.option("--encrypt", is_flag=True, default=False, help="Encrypt the record with a passphrase")
@click.option("--passphrase", default=None, help="Passphrase (required with --encrypt)")
@click.option("--data-dir", default="./engagements")
def export_cmd(engagement_id, out_path, source_ids, label, encrypt, passphrase, data_dir):
    """Package discovery checkpoints into a portable batch record."""
    store = EngagementStore(data_dir=Path(data_dir))
    try:
        path = export_batch_record(
            store, engagement_id, list(source_ids) or None, Path(out_path),
            label=label, encrypt=encrypt, passphrase=passphrase,
        )
    except BatchRecordError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Batch record written: {path}")


@batch_group.command("import")
@click.option("--engagement-id", required=True, help="Engagement ID to import into")
@click.option("--record", "record_path", required=True, type=click.Path(exists=True),
              help="Batch record file to import")
@click.option("--passphrase", default=None, help="Passphrase (for an encrypted record)")
@click.option("--conflict", type=click.Choice(["newest", "refuse"]), default="newest",
              help="On a source already present and differing: keep newest (default) or refuse")
@click.option("--data-dir", default="./engagements")
def import_cmd(engagement_id, record_path, passphrase, conflict, data_dir):
    """Merge a batch record into an engagement; ties the sources in as if live."""
    store = EngagementStore(data_dir=Path(data_dir))
    try:
        result = import_batch_record(
            store, engagement_id, Path(record_path), passphrase=passphrase, conflict=conflict,
        )
    except BatchRecordError as e:
        raise click.ClickException(str(e)) from e
    click.echo(
        f"Imported {len(result.imported)}, replaced {len(result.replaced)}, "
        f"skipped {len(result.skipped)}."
    )
    for sid in result.imported:
        click.echo(f"  + {sid}")
    for sid in result.replaced:
        click.echo(f"  ~ {sid} (newer)")
