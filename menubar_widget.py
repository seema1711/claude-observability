"""macOS menu bar widget — shows live token/cost stats from the observability DB."""
import sys
import os
import webbrowser
from pathlib import Path

# Ensure project root is on sys.path when launched from anywhere
sys.path.insert(0, str(Path(__file__).parent))

import rumps
from core import db
from core.config import DASHBOARD_PORT

# Set process name so it shows as "Claude Observability" in Activity Monitor / Spotlight
try:
    import setproctitle
    setproctitle.setproctitle("Claude Observability")
except ImportError:
    pass

POLL_INTERVAL = 5  # seconds


def _fmt_tokens(n: int) -> str:
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


def _fmt_cost(c: float) -> str:
    return f"${c:.4f}"


class ObservabilityWidget(rumps.App):
    def __init__(self):
        super().__init__("Claude Observability", title="👁", quit_button=None)
        self._last_id = None

        self.last_item   = rumps.MenuItem("Last: —")
        self.today_item  = rumps.MenuItem("Today: —")
        self.alltime_item = rumps.MenuItem("All time: —")
        self.score_item  = rumps.MenuItem("Avg score: —")

        sep1 = rumps.separator
        self.dash_item  = rumps.MenuItem("Open Dashboard", callback=self._open_dashboard)
        self.quit_item  = rumps.MenuItem("Quit", callback=rumps.quit_application)

        self.menu = [
            self.last_item,
            self.today_item,
            self.alltime_item,
            self.score_item,
            None,
            self.dash_item,
            self.quit_item,
        ]

        self._refresh(None)

    @rumps.timer(POLL_INTERVAL)
    def _refresh(self, _):
        try:
            recent = db.get_recent_interactions(limit=1)
            summary = db.get_summary_stats()
            today_stats = db.get_daily_stats(days=1)

            if recent:
                last = recent[0]
                if last["id"] != self._last_id:
                    self._last_id = last["id"]
                tok_in  = last["input_tokens"]
                tok_out = last["output_tokens"]
                cost    = last["cost"]
                score   = last["optimization_score"]
                total   = tok_in + tok_out
                self.title = f"👁 {_fmt_tokens(total)} {_fmt_cost(cost)}"
                self.last_item.title = (
                    f"Last: {_fmt_tokens(total)} tok "
                    f"({_fmt_tokens(tok_in)}↑ {_fmt_tokens(tok_out)}↓) — {_fmt_cost(cost)}"
                )
                self.score_item.title = f"Last score: {score}/100"
            else:
                self.title = "👁 —"
                self.last_item.title = "Last: no interactions yet"

            if today_stats:
                t = today_stats[0]
                today_tok = t["input_tokens"] + t["output_tokens"]
                self.today_item.title = (
                    f"Today: {_fmt_tokens(today_tok)} tok — {_fmt_cost(t['cost'])}"
                )

            all_tok = summary["total_input_tokens"] + summary["total_output_tokens"]
            self.alltime_item.title = (
                f"All time: {_fmt_tokens(all_tok)} tok — {_fmt_cost(summary['total_cost'])}"
            )

        except Exception as e:
            self.title = "👁 err"
            self.last_item.title = f"Error: {e}"

    def _open_dashboard(self, _):
        webbrowser.open(f"http://localhost:{DASHBOARD_PORT}")


if __name__ == "__main__":
    ObservabilityWidget().run()
