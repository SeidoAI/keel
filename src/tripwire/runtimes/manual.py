"""ManualRuntime — prep-only, prints the command for the human to run.

Full lifecycle implementation lands in T9; this scaffold only carries
``validate_environment`` so the prep orchestrator can dispatch to it.
"""


class ManualRuntime:
    name = "manual"

    def validate_environment(self) -> None:
        return
