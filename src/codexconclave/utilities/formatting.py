"""Rich-powered formatting utilities for CodexConclave output.

These helpers produce human-readable, styled terminal output using
the Rich library.  They are called by the Conclave executor and CLI
when verbose output is enabled.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from codexconclave.conclave import ConclaveResult
    from codexconclave.directive import DirectiveResult

logger = logging.getLogger(__name__)

_console = Console()


def format_directive_result(result: DirectiveResult) -> str:
    """Return a human-readable string representation of a directive result.

    Args:
        result: The :class:`~codexconclave.directive.DirectiveResult`
            to format.

    Returns:
        str: Multi-line formatted string.
    """
    lines = [
        f"Directive : {result.description}",
        f"Arbiter   : {result.agent_role}",
        f"Expected  : {result.expected_output}",
        "",
        "Output:",
        result.output,
    ]
    if result.output_file:
        lines.append(f"\nSaved to: {result.output_file}")
    return "\n".join(lines)


def format_conclave_result(result: ConclaveResult) -> str:
    """Return a human-readable summary of a full Conclave execution.

    Args:
        result: The :class:`~codexconclave.conclave.ConclaveResult`
            to format.

    Returns:
        str: Multi-line formatted string.
    """
    parts = ["=== Conclave Result ===", ""]

    for i, dr in enumerate(result.directive_results, start=1):
        parts.append(f"--- Directive {i}: {dr.description[:60]} ---")
        parts.append(f"Arbiter : {dr.agent_role}")
        parts.append(f"Output  : {dr.output[:300]}")
        parts.append("")

    parts.append("=== Final Output ===")
    parts.append(result.final_output)

    if result.token_usage:
        parts.append("")
        parts.append("Token Usage:")
        for k, v in result.token_usage.items():
            parts.append(f"  {k}: {v}")

    return "\n".join(parts)


def print_arbiter_action(
    arbiter_role: str,
    action: str,
    verbose: bool,
) -> None:
    """Print an Arbiter action to the console when verbose is enabled.

    Args:
        arbiter_role: The role label of the acting Arbiter.
        action: A description of what the Arbiter is doing.
        verbose: When ``False``, nothing is printed.
    """
    if not verbose:
        return

    text = Text()
    text.append(f"[{arbiter_role}]", style="bold cyan")
    text.append(f" {action}", style="white")
    _console.print(text)


def print_instrument_use(
    instrument_name: str,
    input_str: str,
) -> None:
    """Print an instrument invocation to the console.

    Displays the instrument name and a truncated version of the input
    so the developer can follow the execution trace.

    Args:
        instrument_name: The registered name of the instrument.
        input_str: The input string passed to the instrument.
    """
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
    )
    table.add_column(style="bold yellow")
    table.add_column(style="white")

    table.add_row("Instrument:", instrument_name)
    table.add_row("Input:", input_str[:200])

    panel = Panel(
        table,
        title="[bold yellow]Using Instrument[/bold yellow]",
        border_style="yellow",
        expand=False,
    )
    _console.print(panel)


def print_conclave_result(result: ConclaveResult) -> None:
    """Pretty-print a :class:`ConclaveResult` to the terminal.

    Args:
        result: The completed Conclave result.
    """
    _console.print(
        Panel(
            result.final_output,
            title="[bold green]Conclave Result[/bold green]",
            border_style="green",
        )
    )
