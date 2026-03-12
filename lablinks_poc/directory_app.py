from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request as FastAPIRequest

from lablinks_poc.models import ClaimManifest, HealthResponse, ResetResponse
from lablinks_poc.storage import JsonSqliteStore


class DirectoryService:
    def __init__(self, store: JsonSqliteStore):
        self.store = store

    def register_claim(self, claim: ClaimManifest) -> ClaimManifest:
        self.store.upsert("claims", claim.claim_id, claim.model_dump(mode="json"))
        return claim

    def list_claims(self, query: str | None = None) -> list[ClaimManifest]:
        claims = [ClaimManifest.model_validate(payload) for payload in self.store.list("claims")]
        if not query:
            return claims
        normalized = query.lower()
        return [
            claim
            for claim in claims
            if normalized in claim.claim_id.lower()
            or normalized in claim.title.lower()
            or normalized in claim.assertion.summary.lower()
            or normalized in claim.assertion.subject.lower()
            or normalized in claim.assertion.predicate.lower()
            or normalized in claim.owner.lab_id.lower()
            or any(normalized in tag.lower() for tag in claim.tags)
        ]

    def get_claim(self, claim_id: str) -> ClaimManifest:
        payload = self.store.get("claims", claim_id)
        if payload is None:
            raise KeyError(claim_id)
        return ClaimManifest.model_validate(payload)

    def reset_demo_state(self) -> ResetResponse:
        cleared_tables = ["claims"]
        self.store.clear_tables(cleared_tables)
        return ResetResponse(status="ok", service="directory", cleared_tables=cleared_tables)


def create_app(db_path: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = DirectoryService(JsonSqliteStore(db_path))
        yield

    app = FastAPI(
        title="LabLinks Directory",
        version="0.1.0",
        summary="Shared claim discovery service for the LabLinks PoC.",
        lifespan=lifespan,
    )

    def get_service(request: FastAPIRequest) -> DirectoryService:
        return request.app.state.service

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="directory")

    @app.post("/claims", response_model=ClaimManifest)
    def post_claim(claim: ClaimManifest, request: FastAPIRequest) -> ClaimManifest:
        return get_service(request).register_claim(claim)

    @app.get("/claims", response_model=list[ClaimManifest])
    def list_claims(request: FastAPIRequest, q: str | None = None) -> list[ClaimManifest]:
        return get_service(request).list_claims(q)

    @app.get("/claims/{claim_id}", response_model=ClaimManifest)
    def get_claim(claim_id: str, request: FastAPIRequest) -> ClaimManifest:
        try:
            return get_service(request).get_claim(claim_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found") from error

    @app.post("/demo/reset", response_model=ResetResponse)
    def reset_demo_state(request: FastAPIRequest) -> ResetResponse:
        return get_service(request).reset_demo_state()

    return app
