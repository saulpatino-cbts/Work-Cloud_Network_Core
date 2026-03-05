import click
from rich.console import Console
console = Console()

@click.command(name="review")
@click.option("--finding-id", default=None, help="Review a specific finding by ID")
@click.option("--approve-all", is_flag=True, help="Approve all pending findings")
def review(finding_id, approve_all):
    """Human architect review gate — REQUIRED before cna report.

    cna report is CLI-BLOCKED until this is complete and signed off.
    Architect can: approve, override severity, add context, flag.
    """
    console.print("[yellow]Phase D: TODO — review workflow[/yellow]")
