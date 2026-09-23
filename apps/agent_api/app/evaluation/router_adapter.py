"""Legacy deterministic routing adapter for frozen evaluation baselines only."""

from __future__ import annotations

from apps.agent_api.app.agents.router import RouterAgent, RouterDecision, RouterRequest


class DeterministicEvaluationRouter:
    """Keep historical evaluator route outcomes out of production composition.

    Phase 11 datasets measure their original deterministic contract. Runtime
    composition injects the provider-backed classifier and never uses this
    adapter; it exists only where an evaluation deliberately has no provider.
    """

    def __init__(self, router: RouterAgent | None = None) -> None:
        self._router = router or RouterAgent()

    def route(self, request: RouterRequest) -> RouterDecision:
        return self._router.route(request)

    async def route_async(self, request: RouterRequest) -> RouterDecision:
        return self.route(request)
