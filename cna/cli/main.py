import click
from rich.console import Console
from cna import __version__

console = Console()

@click.group()
@click.version_option(version=__version__)
def cli():
    """CNA — Cloud Network Assessment Platform

    Multi-cloud network and security architecture discovery,
    AI-assisted analysis, diagram generation, and delivery.
    """
    pass

from cna.cli.commands import (
    init_cmd, discover_cmd, analyze_cmd,
    diagram_cmd, review_cmd, report_cmd,
    publish_cmd, module_cmd
)

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
