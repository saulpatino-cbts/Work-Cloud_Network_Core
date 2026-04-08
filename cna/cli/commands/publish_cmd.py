import click
from rich.console import Console

console = Console()


@click.command(name="publish")
@click.option("--domain", default=None, help="Custom domain for delivery portal")
def publish(domain):
    """Deploy client-facing delivery portal to S3 + CloudFront."""
    console.print("[yellow]Phase F: TODO — S3/CloudFront deployment[/yellow]")
