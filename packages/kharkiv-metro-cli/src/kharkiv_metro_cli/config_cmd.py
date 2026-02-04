"""Config commands for metro CLI."""

from __future__ import annotations

import os
import platform
import subprocess
from typing import Any

import click
from click.exceptions import Exit
from kharkiv_metro_core import Config

from .utils import console


@click.group()
def config_cmd() -> None:
    """Manage configuration."""
    pass


@config_cmd.command(name="show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show current configuration."""
    config: Config = ctx.obj["config"]

    console.print(f"[bold]Config file:[/bold] {config.config_path}")
    console.print(f"[bold]Data directory:[/bold] {config.data_path}")
    console.print(f"[bold]Database:[/bold] {config.get_db_path()}\n")

    console.print("[bold]Settings:[/bold]")
    for section, values in config.to_dict().items():
        console.print(f"\n[cyan][{section}][/cyan]")
        for key, value in values.items():
            console.print(f"  {key} = {value}")


@config_cmd.command(name="set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set configuration value (e.g., 'preferences.language en')."""
    config: Config = ctx.obj["config"]

    # Try to convert value to appropriate type
    typed_value: Any = value
    if value.lower() in ("true", "false"):
        typed_value = value.lower() == "true"
    elif value.isdigit():
        typed_value = int(value)

    config.set(key, typed_value)
    console.print(f"[green]✓[/green] Set {key} = {typed_value}")


@config_cmd.command(name="reset")
@click.confirmation_option(prompt="Are you sure you want to reset config to defaults?")
@click.pass_context
def config_reset(ctx: click.Context) -> None:
    """Reset configuration to defaults."""
    config: Config = ctx.obj["config"]
    config.reset()
    console.print("[green]✓[/green] Configuration reset to defaults")


@config_cmd.command(name="open")
@click.pass_context
def config_open(ctx: click.Context) -> None:
    """Open configuration file in default editor."""
    config: Config = ctx.obj["config"]
    config_path = config.config_path

    # Ensure config exists
    config.ensure_dirs()
    config.create_default()

    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.run(["open", config_path], check=True)
        elif system == "Windows":
            subprocess.run(["start", "", config_path], shell=True, check=True)
        else:  # Linux and other Unix
            # Try xdg-open first, fallback to sensible editors
            try:
                subprocess.run(["xdg-open", config_path], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to $EDITOR or common editors
                editor = os.environ.get("EDITOR", "nano")
                subprocess.run([editor, config_path], check=True)

        console.print(f"[green]✓[/green] Opened {config_path}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to open config: {e}")
        console.print(f"[yellow]Config path:[/yellow] {config_path}")
        raise Exit(1)
