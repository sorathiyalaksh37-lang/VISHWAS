"""
Phase 2: TrustGraph Test Suite for v3 API

Tests the current TrustGraph implementation with v3 API:
- add_contact(name, relation, phone_numbers, typical_amount)
- get_trust_context(caller_number, claimed_identity, claimed_relation)
- check_channel_status() returns (ChannelStatus, context_dict)

Replaces legacy tests from test_trust_engine.py that used outdated API.
"""

import pytest
import json
from sqlalchemy.orm import Session

from app.trust_engine.trust_graph import TrustGraph, ChannelStatus
from app.models.call import Contact


class TestTrustGraphContactManagement:
    """Test contact creation, retrieval, and updates."""
    
    def test_add_contact_basic(self, test_db: Session):
        """Test adding a new contact with basic information."""
        graph = TrustGraph(test_db)
        
        contact = graph.add_contact(
            name="Rajesh Kumar",
            relation="father",
            phone_numbers=["+919876543210"],
            typical_amount=5000.0
        )
        
        assert contact.name == "Rajesh Kumar"
        assert contact.relation == "father"
        assert contact.typical_amount == 5000.0
        
        # Verify phone numbers stored as JSON
        saved_numbers = json.loads(contact.saved_numbers)
        assert "+919876543210" in saved_numbers
        
        print(f"✓ Added contact: {contact.name}")
    
    def test_add_contact_multiple_numbers(self, test_db: Session):
        """Test adding a contact with multiple phone numbers."""
        graph = TrustGraph(test_db)
        
        numbers = ["+919876543210", "+919876543211", "+918765432100"]
        contact = graph.add_contact(
            name="HDFC Bank",
            relation="bank",
            phone_numbers=numbers
        )
        
        saved_numbers = json.loads(contact.saved_numbers)
        assert len(saved_numbers) == 3
        assert all(num in saved_numbers for num in numbers)
        
        print(f"✓ Added contact with {len(numbers)} numbers")
    
    def test_add_contact_minimal(self, test_db: Session):
        """Test adding a contact with only name (minimal info)."""
        graph = TrustGraph(test_db)
        
        contact = graph.add_contact(name="Unknown Friend")
        
        assert contact.name == "Unknown Friend"
        assert contact.relation is None
        assert contact.saved_numbers is None
        assert contact.typical_amount is None
        
        print("✓ Added minimal contact (name only)")
    
    def test_update_existing_contact(self, test_db: Session):
        """Test updating an existing contact adds/updates fields."""
        graph = TrustGraph(test_db)
        
        # Create initial contact
        contact1 = graph.add_contact(
            name="Rajesh Kumar",
            phone_numbers=["+919876543210"]
        )
        initial_id = contact1.id
        
        # Update with more info
        contact2 = graph.add_contact(
            name="Rajesh Kumar",
            relation="father",
            phone_numbers=["+919876543210", "+919876543211"],
            typical_amount=10000.0
        )
        
        # Should be same contact
        assert contact2.id == initial_id
        assert contact2.relation == "father"
        assert contact2.typical_amount == 10000.0
        
        saved_numbers = json.loads(contact2.saved_numbers)
        assert len(saved_numbers) == 2
        
        print("✓ Updated existing contact")
    
    def test_get_contact_by_name(self, test_db: Session):
        """Test retrieving contact by name."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        contact = graph.get_contact_by_name("Rajesh Kumar")
        assert contact is not None
        assert contact.name == "Rajesh Kumar"
        assert contact.relation == "father"
        
        print("✓ Retrieved contact by name")
    
    def test_get_contact_by_name_case_insensitive(self, test_db: Session):
        """Test name lookup is case-insensitive."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        # Should find with different cases
        assert graph.get_contact_by_name("rajesh kumar") is not None
        assert graph.get_contact_by_name("RAJESH KUMAR") is not None
        assert graph.get_contact_by_name("Rajesh KUMAR") is not None
        
        print("✓ Case-insensitive name lookup works")
    
    def test_get_contact_by_relation(self, test_db: Session):
        """Test retrieving contact by relation type."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        contact = graph.get_contact_by_relation("father")
        assert contact is not None
        assert contact.name == "Rajesh Kumar"
        
        print("✓ Retrieved contact by relation")
    
    def test_get_contact_by_phone(self, test_db: Session):
        """Test retrieving contact by phone number."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210", "+918888888888"])
        
        # Should find by either number
        contact1 = graph.get_contact_by_phone("+919876543210")
        assert contact1 is not None
        assert contact1.name == "Rajesh Kumar"
        
        contact2 = graph.get_contact_by_phone("+918888888888")
        assert contact2 is not None
        assert contact2.name == "Rajesh Kumar"
        
        print("✓ Retrieved contact by phone number")
    
    def test_get_contact_not_found(self, test_db: Session):
        """Test lookup returns None for nonexistent contact."""
        graph = TrustGraph(test_db)
        
        assert graph.get_contact_by_name("Nonexistent") is None
        assert graph.get_contact_by_phone("+919999999999") is None
        assert graph.get_contact_by_relation("stranger") is None
        
        print("✓ Missing contacts return None")


class TestTrustGraphChannelStatus:
    """Test channel status verification logic."""
    
    def test_channel_status_verified(self, test_db: Session):
        """Test VERIFIED status when contact and number match."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        status, context = graph.check_channel_status(
            caller_number="+919876543210",
            claimed_identity="Rajesh Kumar"
        )
        
        assert status == ChannelStatus.VERIFIED
        assert context["contact_found"] is True
        assert context["number_matches"] is True
        assert context["contact_name"] == "Rajesh Kumar"
        
        print(f"✓ VERIFIED status: {status}")
    
    def test_channel_status_verified_no_claim(self, test_db: Session):
        """Test VERIFIED status when known number calls without claim."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        # No claimed_identity provided
        status, context = graph.check_channel_status(
            caller_number="+919876543210"
        )
        
        assert status == ChannelStatus.VERIFIED
        assert context["contact_found"] is True
        assert context["contact_name"] == "Rajesh Kumar"
        
        print("✓ VERIFIED without claim (known number)")
    
    def test_channel_status_mismatch(self, test_db: Session):
        """Test MISMATCH status when contact exists but number doesn't match."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        # Different number claims to be Rajesh
        status, context = graph.check_channel_status(
            caller_number="+919999999999",
            claimed_identity="Rajesh Kumar"
        )
        
        assert status == ChannelStatus.MISMATCH
        assert context["contact_found"] is True
        assert context["number_matches"] is False
        assert context["contradiction_type"] == "number_mismatch"
        assert context["contact_name"] == "Rajesh Kumar"
        
        print(f"✓ MISMATCH status: {status}")
    
    def test_channel_status_unknown_no_contact(self, test_db: Session):
        """Test UNKNOWN status when contact doesn't exist."""
        graph = TrustGraph(test_db)
        
        status, context = graph.check_channel_status(
            caller_number="+919999999999",
            claimed_identity="Unknown Person"
        )
        
        assert status == ChannelStatus.UNKNOWN
        assert context["contact_found"] is False
        assert context["number_matches"] is False
        
        print("✓ UNKNOWN status (no contact record)")
    
    def test_channel_status_unknown_no_claim(self, test_db: Session):
        """Test UNKNOWN status when unknown number calls without claim."""
        graph = TrustGraph(test_db)
        
        # No contact exists, no claim made
        status, context = graph.check_channel_status(
            caller_number="+919999999999"
        )
        
        assert status == ChannelStatus.UNKNOWN
        assert context["contact_found"] is False
        
        print("✓ UNKNOWN status (no claim, no contact)")
    
    def test_channel_status_unknown_no_number(self, test_db: Session):
        """Test UNKNOWN status when no caller number provided."""
        graph = TrustGraph(test_db)
        
        status, context = graph.check_channel_status(
            caller_number=None,
            claimed_identity="Someone"
        )
        
        assert status == ChannelStatus.UNKNOWN
        
        print("✓ UNKNOWN status (no caller number)")
    
    def test_channel_status_by_relation_claim(self, test_db: Session):
        """Test channel status when claiming relation instead of name."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        # Claim "father" instead of specific name
        status, context = graph.check_channel_status(
            caller_number="+919876543210",
            claimed_relation="father"
        )
        
        assert status == ChannelStatus.VERIFIED
        assert context["contact_found"] is True
        assert context["number_matches"] is True
        
        print("✓ VERIFIED via relation claim")


class TestTrustGraphContext:
    """Test complete trust context generation."""
    
    def test_get_trust_context_verified(self, test_db: Session):
        """Test complete context for verified contact."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        context = graph.get_trust_context(
            caller_number="+919876543210",
            claimed_identity="Rajesh Kumar"
        )
        
        assert context["channel_status"] == "VERIFIED"
        assert context["contact_found"] is True
        assert context["number_matches"] is True
        assert context["contact_name"] == "Rajesh Kumar"
        assert context["contact_relation"] == "father"
        
        print("✓ Complete trust context (VERIFIED)")
    
    def test_get_trust_context_mismatch(self, test_db: Session):
        """Test complete context for identity mismatch."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        context = graph.get_trust_context(
            caller_number="+919999999999",
            claimed_identity="Rajesh Kumar"
        )
        
        assert context["channel_status"] == "MISMATCH"
        assert context["contact_found"] is True
        assert context["number_matches"] is False
        assert context["contradiction_type"] == "number_mismatch"
        assert context["verification_method"] == "callback_saved_number"
        assert "+919876543210" in context["safe_numbers"]
        
        print("✓ Complete trust context (MISMATCH)")
    
    def test_get_trust_context_unknown(self, test_db: Session):
        """Test complete context for unknown caller."""
        graph = TrustGraph(test_db)
        
        context = graph.get_trust_context(
            caller_number="+919999999999",
            claimed_identity="Unknown Person"
        )
        
        assert context["channel_status"] == "UNKNOWN"
        assert context["contact_found"] is False
        assert "verification_method" not in context or context.get("verification_method") is None
        
        print("✓ Complete trust context (UNKNOWN)")


class TestTrustGraphEdgeCases:
    """Test edge cases and error handling."""
    
    def test_duplicate_contacts_same_name(self, test_db: Session):
        """Test that duplicate contacts are prevented (update instead)."""
        graph = TrustGraph(test_db)
        
        contact1 = graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        contact2 = graph.add_contact("Rajesh Kumar", "uncle", ["+918888888888"])
        
        # Should be same contact ID
        assert contact1.id == contact2.id
        
        # Should have latest values
        assert contact2.relation == "uncle"
        
        # Count contacts in database
        contacts = graph.list_contacts()
        rajesh_contacts = [c for c in contacts if c.name == "Rajesh Kumar"]
        assert len(rajesh_contacts) == 1
        
        print("✓ Duplicate prevention works (updates instead)")
    
    def test_contact_with_empty_phone_list(self, test_db: Session):
        """Test contact with empty phone list treated as None."""
        graph = TrustGraph(test_db)
        
        contact = graph.add_contact("Someone", phone_numbers=[])
        
        # Empty list is treated as None (implementation choice)
        # The add_contact() logic: `if phone_numbers` evaluates False for []
        assert contact.saved_numbers is None
        
        print("✓ Empty phone list handled (stored as None)")
    
    def test_contact_lookup_with_partial_match(self, test_db: Session):
        """Test that partial name matches don't incorrectly match."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Rajesh Kumar Singh", "father", ["+919876543210"])
        
        # "Rajesh" alone should not match "Rajesh Kumar Singh"
        contact = graph.get_contact_by_name("Rajesh")
        assert contact is None
        
        # Full name should match
        contact = graph.get_contact_by_name("Rajesh Kumar Singh")
        assert contact is not None
        
        print("✓ Partial matches don't incorrectly match")
    
    def test_malformed_saved_numbers_graceful(self, test_db: Session):
        """Test that malformed saved_numbers JSON doesn't crash."""
        graph = TrustGraph(test_db)
        
        # Create contact with valid data first
        contact = graph.add_contact("Test", phone_numbers=["+919876543210"])
        
        # Manually corrupt the saved_numbers field
        contact.saved_numbers = "not valid json"
        test_db.commit()
        
        # Should not crash, should return None
        found = graph.get_contact_by_phone("+919876543210")
        assert found is None  # Can't parse, so can't match
        
        print("✓ Malformed JSON handled gracefully")
    
    def test_list_contacts(self, test_db: Session):
        """Test listing all contacts."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Person 1", "friend", ["+911111111111"])
        graph.add_contact("Person 2", "colleague", ["+912222222222"])
        graph.add_contact("Person 3", "family", ["+913333333333"])
        
        contacts = graph.list_contacts(limit=100)
        assert len(contacts) >= 3
        
        names = {c.name for c in contacts}
        assert "Person 1" in names
        assert "Person 2" in names
        assert "Person 3" in names
        
        print(f"✓ Listed {len(contacts)} contacts")
    
    def test_delete_contact(self, test_db: Session):
        """Test deleting a contact."""
        graph = TrustGraph(test_db)
        
        contact = graph.add_contact("To Delete", phone_numbers=["+919999999999"])
        contact_id = contact.id
        
        # Verify exists
        assert graph.get_contact_by_name("To Delete") is not None
        
        # Delete
        result = graph.delete_contact(contact_id)
        assert result is True
        
        # Verify deleted
        assert graph.get_contact_by_name("To Delete") is None
        
        print("✓ Contact deleted successfully")
    
    def test_delete_nonexistent_contact(self, test_db: Session):
        """Test deleting a nonexistent contact returns False."""
        graph = TrustGraph(test_db)
        
        result = graph.delete_contact("fake-uuid-12345")
        assert result is False
        
        print("✓ Deleting nonexistent contact handled")


class TestTrustGraphSafety:
    """Test safety properties: unknown ≠ mismatch, null safety."""
    
    def test_unknown_is_not_mismatch(self, test_db: Session):
        """Critical: UNKNOWN status must not be treated as MISMATCH."""
        graph = TrustGraph(test_db)
        
        # Unknown caller claiming unknown identity
        status, context = graph.check_channel_status(
            caller_number="+919999999999",
            claimed_identity="Unknown Person"
        )
        
        # Should be UNKNOWN, NOT MISMATCH
        assert status == ChannelStatus.UNKNOWN
        assert status != ChannelStatus.MISMATCH
        assert context["contact_found"] is False
        
        print("✓ UNKNOWN ≠ MISMATCH (safety property)")
    
    def test_no_false_verification(self, test_db: Session):
        """Test that only exact matches result in VERIFIED status."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Real Person", "friend", ["+919876543210"])
        
        # Similar but different number should not verify
        status, _ = graph.check_channel_status(
            caller_number="+919876543211",  # One digit different
            claimed_identity="Real Person"
        )
        
        assert status == ChannelStatus.MISMATCH  # Not VERIFIED
        
        print("✓ No false verification (exact match required)")
    
    def test_null_caller_number_safe(self, test_db: Session):
        """Test that None caller_number doesn't crash."""
        graph = TrustGraph(test_db)
        
        graph.add_contact("Someone", phone_numbers=["+919876543210"])
        
        status, context = graph.check_channel_status(
            caller_number=None,
            claimed_identity="Someone"
        )
        
        assert status == ChannelStatus.UNKNOWN
        
        print("✓ None caller_number handled safely")
    
    def test_empty_string_caller_number_safe(self, test_db: Session):
        """Test that empty string caller_number doesn't crash."""
        graph = TrustGraph(test_db)
        
        status, context = graph.check_channel_status(
            caller_number="",
            claimed_identity="Someone"
        )
        
        assert status == ChannelStatus.UNKNOWN
        
        print("✓ Empty string caller_number handled safely")
