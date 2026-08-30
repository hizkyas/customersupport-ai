from typing import Set
from fastapi import HTTPException, status

VALID_STATUSES: Set[str] = {
    "ai_active",
    "waiting_human",
    "human_active",
    "resolved",
    "closed"
}

ALLOWED_TRANSITIONS: dict[str, Set[str]] = {
    "ai_active": {"waiting_human", "resolved", "closed"},
    "waiting_human": {"human_active", "ai_active", "resolved", "closed"},
    "human_active": {"waiting_human", "resolved", "closed"},
    "resolved": {"ai_active", "human_active", "closed"},
    "closed": {"ai_active", "human_active"},
}

def validate_state_transition(current_status: str, target_status: str) -> None:
    """
    Enforce conversation state machine rules.
    Raises HTTPException 400 if transition is invalid.
    """
    if target_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target status '{target_status}'. Allowed: {', '.join(VALID_STATUSES)}"
        )
        
    if current_status == target_status:
        return  # No-op change allowed

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition conversation status from '{current_status}' to '{target_status}'"
        )
