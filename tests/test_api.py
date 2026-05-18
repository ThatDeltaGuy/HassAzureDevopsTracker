"""Tests for the Azure DevOps Tracker API helpers."""

from custom_components.azure_devops_tracker.api import AzureDevOpsClient


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
