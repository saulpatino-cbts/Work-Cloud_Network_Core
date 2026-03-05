import click
from rich.console import Console
console = Console()

@click.command(name="init")
@click.option("--client", required=True, help="Client slug (no spaces)")
@click.option("--regions", default="us", help="Comma-separated: us,emea,japan")
@click.option("--engagement-id", default=None, help="Override engagement ID")
def init(client, regions, engagement_id):
    """Initialize a new assessment engagement."""
    console.print(f"[bold green]Initializing engagement: {client}[/bold green]")
    console.print("[yellow]Phase A: TODO — engagement store creation[/yellow]")
