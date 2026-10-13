"""
Categorized detection patterns for Tier 1 classifier.

All patterns are rule-based and deterministic. No LLM or external API calls.
Patterns support English, Hindi, and common Hinglish expressions.
"""
import re
from typing import Dict, List, Tuple, Literal

# Type aliases for clarity
PatternList = List[Tuple[str, str, float]]  # (pattern, pattern_id, base_confidence)
SeverityType = Literal["low", "medium", "high", "critical"]


class DetectionPatterns:
    """Centralized pattern repository for fraud detection."""
    
    # ========================================================================
    # IDENTITY CLAIM PATTERNS
    # ========================================================================
    
    IDENTITY_CLAIMS: Dict[str, PatternList] = {
        "relative": [
            # English
            (r"\b(i am|i'?m|this is|speaking|calling)\s+(your|tumhara|tumhari)\s+(mother|mom|mummy|ma|maa|amma)\b", "REL_MOTHER_1", 0.9),
            (r"\b(i am|i'?m|this is|speaking|calling)\s+(your|tumhara|tumhari)\s+(father|dad|daddy|papa|pitaji)\b", "REL_FATHER_1", 0.9),
            (r"\b(i am|i'?m|this is|speaking|calling)\s+(your|tumhara|tumhari)\s+(son|beta|bete)\b", "REL_SON_1", 0.9),
            (r"\b(i am|i'?m|this is|speaking|calling)\s+(your|tumhara|tumhari)\s+(daughter|beti|bitiya)\b", "REL_DAUGHTER_1", 0.9),
            (r"\b(i am|i'?m|this is|speaking|calling)\s+(your|tumhara|tumhari)\s+(brother|bhai|bhaiya)\b", "REL_BROTHER_1", 0.9),
            (r"\b(i am|i'?m|this is|speaking|calling)\s+(your|tumhara|tumhari)\s+(sister|behan|didi)\b", "REL_SISTER_1", 0.9),
            
            # Hindi/Hinglish
            (r"\b(mummy|maa|amma|ma)\s+(bol|baat kar|speaking|calling)\s+(rahi|rahe)\s+(hoon|hun|hu)\b", "REL_MOTHER_HI_1", 0.9),
            (r"\b(papa|daddy|pitaji)\s+(bol|baat kar|speaking|calling)\s+(raha|rahe)\s+(hoon|hun|hu)\b", "REL_FATHER_HI_1", 0.9),
            (r"\b(beta|bete|son)\s+(bol|baat kar|speaking|calling)\s+(raha|rahe)\s+(hoon|hun|hu)\b", "REL_SON_HI_1", 0.9),
            (r"\b(beti|bitiya|daughter)\s+(bol|baat kar|speaking|calling)\s+(rahi|rahe)\s+(hoon|hun|hu)\b", "REL_DAUGHTER_HI_1", 0.9),
            (r"\bmain\s+(tumhara|tumhari|aapka|aapki)\s+(mummy|papa|beta|beti|bhai|behan)\s+(hoon|hun|hu)\b", "REL_GENERAL_HI_1", 0.9),
        ],
        
        "organization": [
            # Banks
            (r"\b(i am|i'?m|this is|speaking|calling)\s+(from|se)\s+(your|aapke|tumhare)?\s*(bank|hdfc|icici|sbi|axis|kotak)\b", "ORG_BANK_1", 0.85),
            (r"\b(bank|hdfc|icici|sbi|axis|kotak)\s+(se|from)\s+(call|phone|bol|baat)\s+(kar|calling|speaking)\s+(raha|rahi|rahe)\s+(hoon|hun|hu)\b", "ORG_BANK_HI_1", 0.85),
            (r"\b(calling|speaking|bol raha)\s+(from|se)\s+(the\s+)?(bank|hdfc|icici|sbi|axis|kotak)\b", "ORG_BANK_2", 0.85),
            
            # Government/Official
            (r"\b(i am|i'?m|this is|speaking|calling)\s+(from|se)\s+(government|sarkari|income tax|tax department|aadhar|uidai)\b", "ORG_GOVT_1", 0.85),
            (r"\b(government|sarkari|income tax|aadhar)\s+(office|se|from)\s+(call|phone|bol|baat)\b", "ORG_GOVT_HI_1", 0.85),
            
            # Telecom/Service
            (r"\b(i am|i'?m|this is)\s+(from|se)\s+(customer (service|support|care)|technical support|telecom)\b", "ORG_SERVICE_1", 0.8),
            (r"\bcustomer\s+(care|service|support)\s+(se|from)\s+(call|bol|baat)\b", "ORG_SERVICE_HI_1", 0.8),
            
            # Delivery
            (r"\b(i am|i'?m|this is)\s+(from|se)\s+(amazon|flipkart|swiggy|zomato|courier|delivery)\b", "ORG_DELIVERY_1", 0.75),
        ],
        
        "authority": [
            (r"\b(i am|i'?m|this is)\s+(a\s+)?(police|officer|inspector|constable|cop)\b", "AUTH_POLICE_1", 0.9),
            (r"\b(police|inspector|officer)\s+(se|from|bol|baat)\s+(kar|calling|speaking)\s+(raha|rahi|rahe)\b", "AUTH_POLICE_HI_1", 0.9),
            (r"\b(i am|i'?m|this is)\s+(from|se)\s+(police|thana|station|cyber cell)\b", "AUTH_POLICE_2", 0.9),
            (r"\b(i am|i'?m|this is)\s+(a\s+)?(lawyer|advocate|attorney|legal)\b", "AUTH_LEGAL_1", 0.85),
        ],
    }
    
    # ========================================================================
    # CREDENTIAL REQUEST PATTERNS
    # ========================================================================
    
    CREDENTIAL_REQUESTS: Dict[str, PatternList] = {
        "otp": [
            # Requests to share/tell OTP
            (r"\b(tell|bata|share|bhej|send|give|do|provide|enter)\s+(me\s+)?(your|apna|tumhara|aapka)?\s*(otp|one time password|verification code|code)\b", "CRED_OTP_REQ_1", 0.95),
            (r"\b(otp|verification code|code)\s+(bata|tell|share|bhej|send|give|do|provide)\b", "CRED_OTP_REQ_2", 0.95),
            (r"\b(what|kya|konsa)\s+(is|hai)\s+(your|tumhara|aapka)\s+(otp|verification code|code)\b", "CRED_OTP_REQ_3", 0.95),
            (r"\b(otp|code)\s+(kya|what)\s+(hai|is|aya|aaya|received)\b", "CRED_OTP_REQ_HI_1", 0.95),
            (r"\b(please\s+)?(read|padho|batao|bolo)\s+(the\s+)?(otp|code|verification)\b", "CRED_OTP_REQ_4", 0.95),
            
            # Contextual OTP requests
            (r"\b(need|chahiye|zarurat)\s+(your|tumhara|aapka)\s+(otp|code|verification)\b", "CRED_OTP_REQ_5", 0.9),
            (r"\b(verify|confirm|check)\s+(your|tumhara)\s+(otp|code)\b", "CRED_OTP_REQ_6", 0.85),
        ],
        
        "pin": [
            # PIN requests
            (r"\b(tell|bata|share|bhej|send|give|enter|provide)\s+(me\s+)?(your|apna|tumhara|aapka)?\s*(atm\s+)?(pin|password)\b", "CRED_PIN_REQ_1", 0.95),
            (r"\b(atm|upi|card)\s+(pin|password)\s+(bata|tell|share|kya|what)\b", "CRED_PIN_REQ_2", 0.95),
            (r"\b(enter|type|dal|daalo|dalo)\s+(your|apna|tumhara)?\s*(atm\s+)?(pin|password)\b", "CRED_PIN_REQ_3", 0.9),
        ],
        
        "password": [
            # Password requests
            (r"\b(tell|bata|share|give|provide)\s+(me\s+)?(your|apna|tumhara|aapka)?\s*(account\s+|login\s+)?(password|paasword)\b", "CRED_PASS_REQ_1", 0.95),
            (r"\b(password|paasword)\s+(bata|tell|share|kya|what)\b", "CRED_PASS_REQ_2", 0.95),
            (r"\b(what|kya)\s+(is|hai)\s+(your|tumhara|aapka)\s+(password|paasword)\b", "CRED_PASS_REQ_3", 0.95),
        ],
        
        "cvv": [
            # CVV/Card details
            (r"\b(tell|bata|share|give)\s+(me\s+)?(your|apna|tumhara)?\s*(card\s+)?(cvv|security code|cvc)\b", "CRED_CVV_REQ_1", 0.95),
            (r"\b(cvv|security code)\s+(bata|tell|kya|number)\b", "CRED_CVV_REQ_2", 0.95),
        ],
        
        "account_number": [
            # Account number
            (r"\b(tell|bata|share|confirm|verify)\s+(me\s+)?(your|apna|tumhara)?\s*(bank\s+)?(account\s+number|account no|a/c number)\b", "CRED_ACC_REQ_1", 0.9),
            (r"\b(account\s+number|account no)\s+(bata|tell|kya)\b", "CRED_ACC_REQ_2", 0.9),
        ],
        
        "kyc_details": [
            # KYC information
            (r"\b(need|chahiye|verify|update|complete)\s+(your|apna|tumhara)?\s*(kyc|documents|pan|aadhar|details)\b", "CRED_KYC_REQ_1", 0.85),
            (r"\b(kyc|pan|aadhar)\s+(update|verify|complete|pending|expired)\b", "CRED_KYC_REQ_2", 0.85),
        ],
    }
    
    # ========================================================================
    # MONEY REQUEST PATTERNS
    # ========================================================================
    
    MONEY_REQUESTS: PatternList = [
        # Direct money requests
        (r"\b(send|bhej|bhejo|transfer|de do|dedo|pay|payment)\s+(\d+|some|kuch)?\s*(rupees?|rupaye?|rs\.?|₹|paisa|money|amount)\b", "MONEY_REQ_1", 0.9),
        (r"\b(\d+)\s*(rupees?|rupaye?|rs\.?|₹)\s+(send|bhej|bhejo|transfer|de do|dedo|chahiye|need)\b", "MONEY_REQ_2", 0.95),
        (r"\b(money|paisa|amount|rupaye?)\s+(send|bhej|transfer|de do|chahiye|need)\b", "MONEY_REQ_3", 0.85),
        
        # UPI/Payment specific
        (r"\b(upi|paytm|phonepe|gpay|google pay)\s+(se|through|via|from)?\s*(send|bhej|payment|transfer)\b", "MONEY_REQ_UPI_1", 0.9),
        (r"\b(make|kar|karo|do)\s+(a\s+)?(payment|transaction|transfer)\s+(of\s+)?(\d+)?\b", "MONEY_REQ_4", 0.85),
        
        # Hindi/Hinglish patterns
        (r"\b(paisa|paise|rupaye)\s+(bhej|de|chahiye|zarurat)\b", "MONEY_REQ_HI_1", 0.9),
        (r"\b(\d+)\s+(ka|rupaye)\s+(bhej|transfer|payment)\b", "MONEY_REQ_HI_2", 0.9),
    ]
    
    # ========================================================================
    # URGENCY PATTERNS
    # ========================================================================
    
    URGENCY_PATTERNS: PatternList = [
        # Time limits
        (r"\b(immediately|urgent|urgently|abhi|turant|jaldi|quickly|fast|right now|now)\b", "URGENCY_TIME_1", 0.8),
        (r"\b(within|ke andar|mein)\s+(\d+\s*)?(minutes?|ghante|hours?|din|days?)\b", "URGENCY_TIME_2", 0.75),
        (r"\b(before|pehle|se pehle)\s+(\d+\s*)?(minutes?|hours?|days?|time|waqt)\b", "URGENCY_TIME_3", 0.75),
        
        # Threats
        (r"\b(account|khata)\s+(will be|ho jayega|hoga)?\s*(blocked|block|band|lock|freeze)\b", "URGENCY_THREAT_1", 0.85),
        (r"\b(account|card|service)\s+(deactivate|suspend|cancel|block)\b", "URGENCY_THREAT_2", 0.85),
        (r"\b(legal action|arrest|police|case|complaint|fir)\s+(against|ke khilaf|hoga)\b", "URGENCY_THREAT_3", 0.9),
        
        # Emergency language
        (r"\b(emergency|zaruri|important|serious|critical|problem|issue|musibat)\b", "URGENCY_EMERG_1", 0.7),
        (r"\b(must|zaroor|compulsory|mandatory)\s+(do|karo|kar)\b", "URGENCY_EMERG_2", 0.75),
    ]
    
    # ========================================================================
    # SECRECY PATTERNS
    # ========================================================================
    
    SECRECY_PATTERNS: PatternList = [
        # Don't tell anyone
        (r"\b(don'?t|mat|nahi)\s+(tell|bata|batana|share|bol|bolna)\s+(anyone|kisi|kisi ko|anybody)\b", "SECRECY_DONT_TELL_1", 0.9),
        (r"\b(kisi ko|anyone)\s+(mat|nahi|don'?t)\s+(bata|tell|bol)\b", "SECRECY_DONT_TELL_2", 0.9),
        
        # Secret/Confidential
        (r"\b(keep|rakh|rakho)\s+(it\s+)?(secret|confidential|gupth|chhupakar)\b", "SECRECY_SECRET_1", 0.85),
        (r"\b(this is|yeh)\s+(between|beech|confidential|secret)\b", "SECRECY_SECRET_2", 0.8),
        (r"\b(only\s+)?(between|beech)\s+(us|you and me|hum|humein)\b", "SECRECY_SECRET_3", 0.75),
        
        # Isolation
        (r"\b(alone|akele|khud)\s+(do|kar|karo|handle)\b", "SECRECY_ALONE_1", 0.7),
        (r"\b(by yourself|khud se|akele)\b", "SECRECY_ALONE_2", 0.65),
    ]
    
    # ========================================================================
    # EMOTIONAL PRESSURE PATTERNS
    # ========================================================================
    
    EMOTIONAL_PRESSURE: Dict[str, PatternList] = {
        "fear": [
            (r"\b(lose|kho|gum)\s+(everything|sab|all|money|paisa)\b", "PRESSURE_FEAR_1", 0.75),
            (r"\b(danger|khatre|trouble|musibat|problem)\b", "PRESSURE_FEAR_2", 0.7),
            (r"\b(you will|tum|aap)\s+(regret|pachtaoge|be arrested|jail)\b", "PRESSURE_FEAR_3", 0.8),
        ],
        
        "authority": [
            (r"\b(police|officer|inspector|government|sarkari)\s+(will|hoga|ayega|call|action)\b", "PRESSURE_AUTH_1", 0.75),
            (r"\b(legal|kanuni)\s+(action|notice|case|complaint)\b", "PRESSURE_AUTH_2", 0.8),
        ],
        
        "sympathy": [
            (r"\b(help|madad|bachao|save)\s+(me|mujhe|please)\b", "PRESSURE_SYMP_1", 0.7),
            (r"\b(accident|hadsa|hospital|emergency)\b", "PRESSURE_SYMP_2", 0.75),
        ],
    }
    
    # ========================================================================
    # NEGATION PATTERNS (to avoid false positives)
    # ========================================================================
    
    NEGATION_CONTEXT = [
        r"\b(never|kabhi nahi|mat|don'?t|nahi)\s+",
        r"\b(should not|shouldn'?t|nahi karna|mat karna)\s+",
        r"\b(will not|won'?t|nahi)\s+(ask|puch|request|share)\s+",
        r"\b(do not|don'?t|mat)\s+(give|share|bata|tell)\s+(your|apna|tumhara)\s+",
    ]
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    @staticmethod
    def compile_patterns(pattern_list: PatternList) -> List[Tuple[re.Pattern, str, float]]:
        """Compile regex patterns with flags for case-insensitive matching."""
        return [
            (re.compile(pattern, re.IGNORECASE | re.UNICODE), pattern_id, confidence)
            for pattern, pattern_id, confidence in pattern_list
        ]
    
    @staticmethod
    def compile_pattern_dict(pattern_dict: Dict[str, PatternList]) -> Dict[str, List[Tuple[re.Pattern, str, float]]]:
        """Compile dictionary of pattern lists."""
        return {
            key: DetectionPatterns.compile_patterns(patterns)
            for key, patterns in pattern_dict.items()
        }
    
    @staticmethod
    def check_negation(text: str, match_start: int, context_window: int = 50) -> bool:
        """
        Check if a match is negated by surrounding context.
        
        Args:
            text: Full text
            match_start: Start position of the match
            context_window: Number of characters to look back
            
        Returns:
            True if match appears to be negated
        """
        # Extract context before the match
        start_pos = max(0, match_start - context_window)
        context = text[start_pos:match_start]
        
        # Check for negation patterns
        for neg_pattern in DetectionPatterns.NEGATION_CONTEXT:
            if re.search(neg_pattern, context, re.IGNORECASE):
                return True
        
        return False
