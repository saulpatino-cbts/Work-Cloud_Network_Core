import click
from rich.console import Console

from cna import __version__
from cna.cli.commands import (
    analyze_cmd,
    diagram_cmd,
    discover_cmd,
    init_cmd,
    module_cmd,
    publish_cmd,
    report_cmd,
    review_cmd,
)

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """CNA — Cloud Network Assessment Platform

    Multi-cloud network and security architecture discovery,
    AI-assisted analysis, diagram generation, and delivery.
    """
    pass


cli.add_command(init_cmd.init)
cli.add_command(discover_cmd.discover)
cli.add_command(analyze_cmd.analyze)
cli.add_command(diagram_cmd.diagram)
cli.add_command(review_cmd.review)
cli.add_command(report_cmd.report)
cli.add_command(publish_cmd.publish)
cli.add_command(module_cmd.module)

if __name__ == "__main__":
    cli()
