"""Health check panel widget for displaying provider health status."""

from __future__ import annotations

import asyncio

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from ..services import HealthService


class HealthPanel(Static):
    """Display health status for transcription providers.

    Features:
    - Shows health status for all providers (Deepgram, ElevenLabs, Whisper, Parakeet)
    - Color-coded status indicators
    - Response time display
    - Auto-refresh every 30 seconds
    - Manual refresh with 'r' key

    Status Colors:
    - Green: Healthy (< 2s response)
    - Yellow: Degraded (2-5s response)
    - Red: Unhealthy (> 5s or error)
    - Gray: Unknown (not checked)

    Example:
        >>> panel = HealthPanel()
        >>> panel.refresh_health()
    """

    CSS = """
    HealthPanel {
        height: auto;
        border: solid $panel;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        """Initialize health panel."""
        super().__init__(**kwargs)
        self._health_service = HealthService()
        self._health_status: dict[str, dict] = {}
        self._check_task: asyncio.Task | None = None

    def on_mount(self) -> None:
        """Set up refresh timer on mount."""
        # Refresh health on mount
        self.refresh_health()

        # Auto-refresh every 30 seconds
        self.set_interval(30.0, self.refresh_health)

    def refresh_health(self) -> None:
        """Refresh health status for all providers."""
        # Run health check in background
        self._check_task = asyncio.create_task(self._check_health())

    async def _check_health(self) -> None:
        """Check health status asynchronously."""
        try:
            results = await self._health_service.check_all_providers()
        except Exception as exc:  # pragma: no cover - defensive logging only
            self.update(f"[red]Error checking health: {exc}[/red]")
            return

        # Normalize status structure for rendering
        normalized: dict[str, dict[str, str | bool | None]] = {}
        for provider, status in results.items():
            provider_status = status or {}
            state = str(provider_status.get("status", "")).lower()
            healthy = state in {"ok", "healthy", "available"}
            normalized[provider] = {
                "healthy": healthy,
                "response_time": provider_status.get("response_time"),
                "message": provider_status.get("message")
                or provider_status.get("details")
                or provider_status.get("error")
                or ("OK" if healthy else "Unknown"),
                "error": provider_status.get("error"),
            }

        self._health_status = normalized
        self._update_display()

    def _update_display(self) -> None:
        """Update the health status display."""
        if not self._health_status:
            self.update("[dim]No provider health data available.[/dim]")
            return

        table = Table(title="Provider Health Status", show_header=True)
        table.add_column("Provider", style="cyan", width=12)
        table.add_column("Status", width=10)
        table.add_column("Response Time", width=15)
        table.add_column("Details", no_wrap=False)

        for provider, status in self._health_status.items():
            if status.get("healthy"):
                status_text = "[green]✓ Healthy[/green]"
            elif status.get("error"):
                status_text = "[red]✗ Error[/red]"
            else:
                status_text = "[yellow]⚠ Degraded[/yellow]"

            # Format response time
            response_time = status.get("response_time")
            if response_time is not None:
                time_text = f"{response_time:.2f}s"
                # Color code by speed
                if response_time < 2.0:
                    time_text = f"[green]{time_text}[/green]"
                elif response_time < 5.0:
                    time_text = f"[yellow]{time_text}[/yellow]"
                else:
                    time_text = f"[red]{time_text}[/red]"
            else:
                time_text = "[dim]--[/dim]"

            # Get details
            details = status.get("message") or status.get("error", "OK")
            if len(details) > 40:
                details = details[:37] + "..."

            table.add_row(provider.capitalize(), status_text, time_text, details)

        footer = Text("Auto-refreshes every 30s. Press 'r' to refresh manually.", style="dim")
        self.update(Group(table, footer))

    def action_refresh(self) -> None:
        """Manual refresh action."""
        self.refresh_health()
        self.notify("Refreshing provider health...", timeout=2)
