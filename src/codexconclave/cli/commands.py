"""CLI commands for the CodexConclave framework.

Invoked via the ``codex`` entry-point defined in ``pyproject.toml``.

Usage::

    codex create conclave my_project
    codex create cascade my_pipeline
    codex run
    codex chat "machine learning trends"
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project scaffolding templates
# ---------------------------------------------------------------------------

_CONCLAVE_MAIN = '''\
"""CodexConclave project: {name}."""
from codexconclave import Arbiter, Conclave, Directive, Protocol
from codexconclave.llm import LLMProvider


def build_conclave() -> Conclave:
    """Construct and return the Conclave."""
    llm = LLMProvider(model="gpt-4o")

    researcher = Arbiter(
        role="Researcher",
        objective="Research the given topic thoroughly.",
        persona="You are an expert researcher with broad knowledge.",
        llm=llm,
    )

    writer = Arbiter(
        role="Writer",
        objective="Write clear, engaging content.",
        persona="You are a skilled technical writer.",
        llm=llm,
    )

    research_task = Directive(
        description="Research {name} and summarise key findings.",
        expected_output="A comprehensive research summary.",
        arbiter=researcher,
    )

    write_task = Directive(
        description="Write a report based on the research.",
        expected_output="A well-structured written report.",
        arbiter=writer,
        context=[research_task],
    )

    return Conclave(
        arbiters=[researcher, writer],
        directives=[research_task, write_task],
        protocol=Protocol.sequential,
        verbose=True,
    )


if __name__ == "__main__":
    conclave = build_conclave()
    result = conclave.assemble()
    print(result)
'''

_CASCADE_MAIN = '''\
"""CodexConclave Cascade project: {name}."""
from codexconclave.cascade import Cascade, CascadeState, initiate, observe
from pydantic import BaseModel


class {class_name}State(CascadeState):
    """Pipeline state for {name}."""
    input_data: str = ""
    result: str = ""


class {class_name}Pipeline(Cascade):
    """{name} pipeline."""

    state: {class_name}State = {class_name}State()

    @initiate
    def start(self) -> str:
        """Entry point — return the initial input."""
        self.state.input_data = "Hello from {name}"
        return self.state.input_data

    @observe(start)
    def process(self, data: str) -> str:
        """Process the input data."""
        self.state.result = data.upper()
        return self.state.result


if __name__ == "__main__":
    pipeline = {class_name}Pipeline()
    result = pipeline.execute()
    print(f"Completed: {{result.completed_methods}}")
    print(f"State: {{result.final_state}}")
'''

_REQUIREMENTS = """\
codexconclave>=1.0.0
python-dotenv>=1.0.0
"""


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="codexconclave")
def main() -> None:
    """CodexConclave — AI agent team orchestration framework."""


# ---------------------------------------------------------------------------
# create group
# ---------------------------------------------------------------------------


@main.group()
def create() -> None:
    """Scaffold new CodexConclave projects."""


@create.command()
@click.argument("name")
def conclave(name: str) -> None:
    """Create a new Conclave project in a directory called NAME.

    Args:
        name: The project name (also becomes the directory name).
    """
    project_dir = Path(name)

    if project_dir.exists():
        click.echo(f"Error: directory '{name}' already exists.", err=True)
        sys.exit(1)

    project_dir.mkdir(parents=True)

    main_file = project_dir / "main.py"
    main_file.write_text(_CONCLAVE_MAIN.format(name=name), encoding="utf-8")

    req_file = project_dir / "requirements.txt"
    req_file.write_text(_REQUIREMENTS, encoding="utf-8")

    env_file = project_dir / ".env.example"
    env_file.write_text("OPENAI_API_KEY=your-api-key-here\n", encoding="utf-8")

    click.echo(
        f"Created Conclave project '{name}' in ./{name}/\n"
        f"  {main_file}\n"
        f"  {req_file}\n"
        f"  {env_file}\n\n"
        f"Next steps:\n"
        f"  cd {name}\n"
        f"  cp .env.example .env  # and add your API key\n"
        f"  python main.py"
    )


@create.command()
@click.argument("name")
def cascade(name: str) -> None:
    """Create a new Cascade pipeline project in a directory called NAME.

    Args:
        name: The project name (also becomes the directory name).
    """
    project_dir = Path(name)

    if project_dir.exists():
        click.echo(f"Error: directory '{name}' already exists.", err=True)
        sys.exit(1)

    project_dir.mkdir(parents=True)

    # PascalCase class name from hyphenated/snake name
    class_name = "".join(
        part.capitalize() for part in name.replace("-", "_").split("_")
    )

    main_file = project_dir / "main.py"
    main_file.write_text(
        _CASCADE_MAIN.format(name=name, class_name=class_name),
        encoding="utf-8",
    )

    req_file = project_dir / "requirements.txt"
    req_file.write_text(_REQUIREMENTS, encoding="utf-8")

    click.echo(
        f"Created Cascade project '{name}' in ./{name}/\n"
        f"  {main_file}\n"
        f"  {req_file}\n\n"
        f"Next steps:\n"
        f"  cd {name}\n"
        f"  python main.py"
    )


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--file",
    "-f",
    default="main.py",
    show_default=True,
    help="Python file containing the Conclave or Cascade to run.",
)
def run(file: str) -> None:
    """Execute the Conclave or Cascade defined in FILE.

    Looks for a ``build_conclave()`` function to build and
    ``assemble()`` a Conclave, or a class derived from ``Cascade``
    with an ``execute()`` method.
    """
    path = Path(file)
    if not path.exists():
        click.echo(
            f"Error: '{file}' not found in current directory.",
            err=True,
        )
        sys.exit(1)

    # Load the module dynamically
    import importlib.util

    spec = importlib.util.spec_from_file_location("_user_module", path)
    if spec is None or spec.loader is None:
        click.echo(f"Error: cannot load '{file}'.", err=True)
        sys.exit(1)

    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        click.echo(f"Error loading '{file}': {exc}", err=True)
        sys.exit(1)

    # Try Conclave
    if hasattr(mod, "build_conclave"):
        click.echo("Running Conclave...")
        try:
            conclave_obj = mod.build_conclave()
            result = conclave_obj.assemble()
            click.echo(str(result))
        except Exception as exc:
            click.echo(f"Conclave execution failed: {exc}", err=True)
            sys.exit(1)
        return

    # Try Cascade — find a Cascade subclass
    from codexconclave.cascade import Cascade as CascadeBase

    cascade_classes = [
        v
        for v in vars(mod).values()
        if (
            isinstance(v, type)
            and issubclass(v, CascadeBase)
            and v is not CascadeBase
        )
    ]

    if cascade_classes:
        click.echo(f"Running Cascade: {cascade_classes[0].__name__}...")
        try:
            pipeline = cascade_classes[0]()
            result = pipeline.execute()
            click.echo(f"Completed methods: {result.completed_methods}")
        except Exception as exc:
            click.echo(f"Cascade execution failed: {exc}", err=True)
            sys.exit(1)
        return

    click.echo(
        "Error: no `build_conclave()` function or Cascade subclass "
        f"found in '{file}'.",
        err=True,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# chat command
# ---------------------------------------------------------------------------


@main.command()
@click.argument("topic")
@click.option(
    "--model",
    "-m",
    default="gpt-4o",
    show_default=True,
    help="LLM model to use for the chat.",
)
def chat(topic: str, model: str) -> None:
    """Start an interactive chat with a single Arbiter about TOPIC.

    Press Ctrl+C or type 'exit' / 'quit' to end the session.

    Args:
        topic: The topic to discuss.
        model: The LLM model identifier to use.
    """
    from codexconclave import Arbiter, Directive
    from codexconclave.llm import LLMProvider

    llm = LLMProvider(model=model)
    arbiter = Arbiter(
        role="Assistant",
        objective=f"Help the user with questions about: {topic}",
        persona=(
            "You are a knowledgeable and helpful AI assistant "
            f"specialising in {topic}."
        ),
        llm=llm,
        verbose=False,
    )

    click.echo(
        f"Starting chat about '{topic}' (model: {model}). "
        "Type 'exit' or 'quit' to stop.\n"
    )

    while True:
        try:
            user_input = click.prompt("You")
        except (click.Abort, EOFError):
            click.echo("\nGoodbye!")
            break

        if user_input.strip().lower() in ("exit", "quit"):
            click.echo("Goodbye!")
            break

        directive = Directive(
            description=user_input,
            expected_output="A helpful, informative response.",
        )

        try:
            result = arbiter.perform(directive)
            click.echo(f"\nAssistant: {result.output}\n")
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
