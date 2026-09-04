"""Reserved attendance route module.

The POST endpoint is deliberately not implemented during backend preparation.
Its contract is documented in docs/API_CONTRACT.md and its schemas are ready
for the next approved milestone.
"""

from fastapi import APIRouter


router = APIRouter(prefix="/api/v1", tags=["attendance"])
