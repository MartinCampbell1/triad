"""Triad CLI — entry point."""
from __future__ import annotations

import typer

app = typer.Typer(
    name="triad",
    help="Local orchestration control-plane for AI coding CLIs",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    mode: str | None = typer.Option(None, "--mode", "-m", help="Start in mode: solo, critic, delegate"),
):
    """Launch Triad TUI."""
    if ctx.invoked_subcommand is not None:
        return
    from triad.tui.app import TriadApp
    t = TriadApp()
    t.run()


@app.command()
def accounts():
    """Show account status."""
    from pathlib import Path
    from triad.core.accounts.manager import AccountManager

    profiles_dir = Path.home() / ".cli-profiles"
    if not profiles_dir.exists():
        typer.echo(f"No profiles directory found at {profiles_dir}")
        raise typer.Exit(1)

    mgr = AccountManager(profiles_dir=profiles_dir)
    mgr.discover()

    if not mgr.pools:
        typer.echo("No profiles found.")
        raise typer.Exit(0)

    for provider, profiles in mgr.pools.items():
        typer.echo(f"\n{provider}: {len(profiles)} account(s)")
        for p in profiles:
            status = "✓" if p.check_available() else "✗ (cooldown)"
            typer.echo(f"  {p.name} {status}  requests={p.requests_made}")


@app.command()
def sessions():
    """List recent sessions."""
    import asyncio
    from pathlib import Path
    from triad.core.storage.ledger import Ledger

    async def _list():
        db_path = Path.home() / ".triad" / "triad.db"
        if not db_path.exists():
            typer.echo("No sessions found. (Database not yet created)")
            return
        lg = Ledger(db_path=db_path)
        await lg.initialize()
        items = await lg.list_sessions(limit=20)
        await lg.close()
        if not items:
            typer.echo("No sessions found.")
            return
        for s in items:
            typer.echo(f"  {s['id']}  {s['mode']:10s}  {s['status']:10s}  {s['task'][:60]}")

    asyncio.run(_list())


if __name__ == "__main__":
    app()
