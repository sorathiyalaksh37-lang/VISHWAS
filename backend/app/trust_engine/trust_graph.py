"""
Trust Graph implementation for VISHWAS.

Manages relationship and communication channel context.
Uses existing Contact model from database for persistence.

Key Principle: Unknown != Fraudulent
Missing context means UNKNOWN, not MISMATCH.
"""
import logging
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.call import Contact

logger = logging.getLogger(__name__)


class ChannelStatus(str, Enum):
    """Communication channel verification status."""
    VERIFIED = "VERIFIED"      # Known contact using verified number
    UNKNOWN = "UNKNOWN"        # No relationship context available
    MISMATCH = "MISMATCH"      # Claim conflicts with verified data
    STALE = "STALE"           # Data exists but may be outdated


class TrustGraph:
    """
    Lightweight Trust Graph for relationship and channel context.
    
    Responsibilities:
    - Store and retrieve known contacts
    - Compare claimed identity with verified relationships
    - Assess communication channel status
    - Identify contradictions with supporting evidence
    
    NOT responsible for:
    - Final risk scoring
    - Making fraud determinations
    - Automatically collecting contact data
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize Trust Graph with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        logger.info("TrustGraph initialized")
    
    def add_contact(
        self,
        name: str,
        relation: Optional[str] = None,
        phone_numbers: Optional[List[str]] = None,
        typical_amount: Optional[float] = None,
    ) -> Contact:
        """
        Add or update a trusted contact.
        
        Args:
            name: Contact name
            relation: Relationship type (e.g., 'mother', 'bank')
            phone_numbers: List of verified phone numbers
            typical_amount: Typical transaction amount
            
        Returns:
            Created or updated Contact model
        """
        import json
        
        # Check for existing contact by name
        existing = self.db.query(Contact).filter(
            Contact.name == name
        ).first()
        
        if existing:
            # Update existing contact
            if relation:
                existing.relation = relation
            if phone_numbers:
                existing.saved_numbers = json.dumps(phone_numbers)
            if typical_amount is not None:
                existing.typical_amount = typical_amount
            
            self.db.commit()
            self.db.refresh(existing)
            logger.info(f"Updated contact: {name}")
            return existing
        else:
            # Create new contact
            contact = Contact(
                name=name,
                relation=relation,
                saved_numbers=json.dumps(phone_numbers) if phone_numbers else None,
                typical_amount=typical_amount,
            )
            self.db.add(contact)
            self.db.commit()
            self.db.refresh(contact)
            logger.info(f"Added new contact: {name}")
            return contact
    
    def get_contact_by_name(self, name: str) -> Optional[Contact]:
        """Retrieve contact by name (case-insensitive)."""
        return self.db.query(Contact).filter(
            Contact.name.ilike(name)  # Case-insensitive match
        ).first()
    
    def get_contact_by_relation(self, relation: str) -> Optional[Contact]:
        """Retrieve contact by relationship type (e.g., 'mother')."""
        return self.db.query(Contact).filter(
            Contact.relation == relation.lower()
        ).first()
    
    def get_contact_by_phone(self, phone: str) -> Optional[Contact]:
        """Retrieve contact by phone number."""
        import json
        
        contacts = self.db.query(Contact).filter(
            Contact.saved_numbers.isnot(None)
        ).all()
        
        for contact in contacts:
            try:
                numbers = json.loads(contact.saved_numbers)
                if phone in numbers:
                    return contact
            except (json.JSONDecodeError, TypeError):
                continue
        
        return None
    
    def check_channel_status(
        self,
        caller_number: Optional[str],
        claimed_identity: Optional[str] = None,
        claimed_relation: Optional[str] = None,
    ) -> tuple[ChannelStatus, Dict[str, Any]]:
        """
        Assess communication channel status.
        
        Args:
            caller_number: Phone number of caller
            claimed_identity: Specific identity claimed (e.g., "Mom", "HDFC Bank")
            claimed_relation: Relationship type claimed (e.g., "mother", "bank")
            
        Returns:
            Tuple of (ChannelStatus, context_dict)
            
        Logic:
        - VERIFIED: Known contact using verified number
        - MISMATCH: Claim conflicts with verified data
        - UNKNOWN: No relationship context available
        """
        import json
        
        context: Dict[str, Any] = {
            "caller_number": caller_number,
            "claimed_identity": claimed_identity,
            "claimed_relation": claimed_relation,
            "contact_found": False,
            "number_matches": False,
            "contradiction_type": None,
        }
        
        # No caller number - cannot verify
        if not caller_number:
            return ChannelStatus.UNKNOWN, context
        
        # No claim made - unknown identity
        if not claimed_identity and not claimed_relation:
            # Check if number is known
            contact = self.get_contact_by_phone(caller_number)
            if contact:
                context["contact_found"] = True
                context["contact_name"] = contact.name
                context["contact_relation"] = contact.relation
                return ChannelStatus.VERIFIED, context
            return ChannelStatus.UNKNOWN, context
        
        # Look up claimed contact
        contact = None
        if claimed_identity:
            contact = self.get_contact_by_name(claimed_identity)
        if not contact and claimed_relation:
            contact = self.get_contact_by_relation(claimed_relation)
        
        # No record of claimed contact - UNKNOWN
        if not contact:
            context["contact_found"] = False
            return ChannelStatus.UNKNOWN, context
        
        # Contact exists - check if number matches
        context["contact_found"] = True
        context["contact_name"] = contact.name
        context["contact_relation"] = contact.relation
        
        if contact.saved_numbers:
            try:
                verified_numbers = json.loads(contact.saved_numbers)
                context["verified_numbers"] = verified_numbers
                
                if caller_number in verified_numbers:
                    context["number_matches"] = True
                    return ChannelStatus.VERIFIED, context
                else:
                    # MISMATCH: Claimed known contact but different number
                    context["number_matches"] = False
                    context["contradiction_type"] = "number_mismatch"
                    return ChannelStatus.MISMATCH, context
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Invalid saved_numbers for contact {contact.name}")
        
        # Contact exists but no verified numbers stored - UNKNOWN
        return ChannelStatus.UNKNOWN, context
    
    def get_trust_context(
        self,
        caller_number: Optional[str],
        claimed_identity: Optional[str] = None,
        claimed_relation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get complete trust context for risk assessment.
        
        Returns:
            Dictionary with:
            - channel_status
            - contact information (if available)
            - contradiction details (if any)
            - verification suggestions
        """
        channel_status, context = self.check_channel_status(
            caller_number,
            claimed_identity,
            claimed_relation
        )
        
        result = {
            "channel_status": channel_status.value,
            "caller_number": caller_number,
            "claimed_identity": claimed_identity,
            "claimed_relation": claimed_relation,
            **context
        }
        
        # Add verification recommendations
        if channel_status == ChannelStatus.MISMATCH and context.get("contact_found"):
            result["verification_method"] = "callback_saved_number"
            result["safe_numbers"] = context.get("verified_numbers", [])
        
        return result
    
    def list_contacts(self, limit: int = 100) -> List[Contact]:
        """List all stored contacts (for debugging/admin)."""
        return self.db.query(Contact).limit(limit).all()
    
    def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact by ID."""
        contact = self.db.query(Contact).filter(Contact.id == contact_id).first()
        if contact:
            self.db.delete(contact)
            self.db.commit()
            logger.info(f"Deleted contact: {contact_id}")
            return True
        return False
