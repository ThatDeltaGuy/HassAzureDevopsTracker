"""Tests for the Azure DevOps Tracker API helpers."""

import asyncio

from custom_components.azure_devops_tracker.api import AzureDevOpsClient
from custom_components.azure_devops_tracker.api import AzureDevOpsAuthError


def test_chunk_splits_values_into_even_groups() -> None:
    """Chunking should preserve order and group by size."""
    values = [str(index) for index in range(1, 8)]

    chunks = AzureDevOpsClient._chunk(values, 3)

    assert chunks == [["1", "2", "3"], ["4", "5", "6"], ["7"]]


def test_parse_identity_returns_basic_fields() -> None:
    """Identity parsing should normalize the expected keys."""
    identity = AzureDevOpsClient._parse_identity(
        {
            "id": "user-1",
            "displayName": "Alex Lund",
            "emailAddress": "alex@example.com",
        }
    )

    assert identity.id == "user-1"
    assert identity.display_name == "Alex Lund"
    assert identity.unique_name == "alex@example.com"


def test_get_current_user_falls_back_to_connection_data() -> None:
    """Profile-host auth failures should fall back to connection data."""

    class _FallbackClient(AzureDevOpsClient):
        def __init__(self) -> None:
            pass

        async def _request_json(self, method, url, *, params=None, json_data=None):
            if "profile/profiles/me" in url:
                raise AzureDevOpsAuthError("Authentication failed")
            return {
                "authenticatedUser": {
                    "id": "user-123",
                    "providerDisplayName": "Alex Lund",
                    "uniqueName": "alex@example.com",
                }
            }

    identity = asyncio.run(_FallbackClient().get_current_user())

    assert identity.id == "user-123"
    assert identity.display_name == "Alex Lund"
    assert identity.unique_name == "alex@example.com"
