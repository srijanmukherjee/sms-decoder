import abc
from dataclasses import dataclass
import json
from typing import Dict, List
import re


@dataclass
class SMS:
    address: str
    body: str


class TransactionSMSDecoder(abc.ABC):
    SMS_TYPE_FIELD = "sms_type"
    TNX_TYPE_FIELD = "tnx_type"
    SENDER_FIELD = "sender"
    RECEIVER_FIELD = "receiver"
    DATE_FIELD = "date"
    REF_NO_FIELD = "ref_no"
    AMOUNT_FIELD = "amount"

    patterns = {}
    debit_keywords = ["debited", "automatic payment of", " dr ", "withdrawn"]
    credit_keywords = ["received", "credited", " cr ", "deposited"]
    legal_tnx_keywords = [
        "received",
        "debited",
        "credited",
        "withdrawn",
        "deposited",
        " cr ",
        " dr ",
    ]
    illegal_tnx_keywords = []

    def decode(self, sms: SMS) -> Dict[str, str]:
        result = {}
        result[TransactionSMSDecoder.SMS_TYPE_FIELD] = self.is_transaction_sms(sms)
        if result[TransactionSMSDecoder.SMS_TYPE_FIELD] is False:
            return result

        result[TransactionSMSDecoder.TNX_TYPE_FIELD] = self.get_tnx_type(sms)

        patterns = self.patterns.get(result[TransactionSMSDecoder.TNX_TYPE_FIELD], [])

        for pattern in patterns:
            match = re.match(pattern["pattern"], sms.body)
            if match is not None:
                result[TransactionSMSDecoder.SENDER_FIELD] = None
                result[TransactionSMSDecoder.RECEIVER_FIELD] = None
                result[TransactionSMSDecoder.DATE_FIELD] = None
                result[TransactionSMSDecoder.REF_NO_FIELD] = None
                result[TransactionSMSDecoder.AMOUNT_FIELD] = None
                groups = match.groups()
                for attribute, pos in pattern["attributes"].items():
                    result[attribute] = groups[pos]
                break

        return result

    def is_transaction_sms(self, sms: SMS) -> bool:
        return any(keyword in sms.body for keyword in self.legal_tnx_keywords) and all(
            keyword not in sms.body for keyword in self.illegal_tnx_keywords
        )

    def get_tnx_type(self, sms: SMS) -> str:
        for keyword in self.debit_keywords:
            if keyword in sms.body:
                return "debit"

        for keyword in self.credit_keywords:
            if keyword in sms.body:
                return "credit"

        return "unknown"


class PaytmTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "debit": [
            {
                "pattern": r"([a-z\d\.]+) is debited from your account ([a-z\d]+) for debit card annual charges of [a-z\d\.]+\. remaining amount to be debited [a-z\d\.]+\. ref id ([\d]+) :ppbl",
                "attributes": {"amount": 0, "sender": 1, "ref_no": 2},
            },
            {
                "pattern": r"your automatic payment of ([a-z\d\.]+) has been successfully executed on ([\d\-]+) towards ([a-z ]+), ([\d]+)\. [\W\w]+ :ppbl",
                "attributes": {"amount": 0, "date": 1, "receiver": 2, "ref_no": 3},
            },
        ],
        "credit": [
            {
                "pattern": r"received ([a-z\d\.]+) in your a/c ([a-z\d]+) from ([a-z\d ]+) on ([\d\-]+)\.ref no: ([a-z\d]+)\. queries\? call ([\d]+) :ppbl",
                "attributes": {
                    "amount": 0,
                    "receiver": 1,
                    "sender": 2,
                    "date": 3,
                    "ref_no": 4,
                },
            },
            {
                "pattern": r"received ([a-z\d\.]+) in your a/c ([a-z\d]+) from ([a-z\d /()]+) on ([\d\-]+)\. (neft|imps) ref no: ([a-z\d]+)\. (queries\? call [\d]+ )?:ppbl",
                "attributes": {
                    "amount": 0,
                    "receiver": 1,
                    "sender": 2,
                    "date": 3,
                    "ref_no": 5,
                },
            },
            {
                "pattern": r"([a-z\d\.]+) has been credited back to your account ([x \d]+)\. upi ref no: ([\d]+) :ppbl",
                "attributes": {"amount": 0, "receiver": 1, "ref_no": 2},
            },
            {
                "pattern": r"([a-z\d\.]+) received from ([a-z\d ]+) in your paytm payments bank a/c ([a-z\d]+)\. upi ref: ([\d]+) avl bal: [a-z\d\.]+\. :ppbl",
                "attributes": {"amount": 0, "sender": 1, "receiver": 2, "ref_no": 3},
            },
            {
                "pattern": r"([a-z \d\.,]+) deposited in your paytm wallet linked with mobile no .*",
                "attributes": {"amount": 0},
            },
        ],
    }

    illegal_tnx_keywords = ["will be"]
    legal_tnx_keywords = TransactionSMSDecoder.legal_tnx_keywords + [
        "successfully executed"
    ]


class IcicibTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "credit": [
            {
                "pattern": r"your icici bank acct ([x\d]+) is credited with ([a-z\d\. ]+) on ([a-z\d\-]+) by acct ([x\d]+)\. imps ref\. no\. ([\d]+)\.",
                "attributes": {
                    "amount": 1,
                    "receiver": 0,
                    "sender": 3,
                    "date": 2,
                    "ref_no": 4,
                },
            },
            {
                "pattern": r"dear customer, acct ([x\d]+) is credited with ([a-z\d\. ]+) on ([a-z\d\-]+) from ([a-z \d\.]+)\. upi:([\d]+)-icici bank\.",
                "attributes": {
                    "amount": 1,
                    "receiver": 0,
                    "date": 2,
                    "sender": 3,
                    "ref_no": 4,
                },
            },
            {
                "pattern": r"icici bank account ([x\d]+) is credited with ([a-z\d\. ,]+) on ([a-z\-\d]+) by account linked to mobile number .+\. imps ref\. no\. ([\d]+)\.",
                "attributes": {"amount": 1, "receiver": 0, "date": 2, "ref_no": 3},
            },
            {
                "pattern": r"dear customer, your icici bank account ([x\d]+) has been credited with ([a-z\d\. ,]+) on ([\da-z\-]+)\. info:.+\. the available balance is .+",
                "attributes": {"amount": 1, "receiver": 0, "date": 2},
            },
            {
                "pattern": r"your icici bank acct ([x\d]+) is credited with ([a-z \d\.,]+) on ([a-z\d\-]+) by acct ([x\d]+)\. imps ref\. no\. ([\d]+)\.",
                "attributes": {
                    "amount": 1,
                    "receiver": 0,
                    "date": 2,
                    "sender": 3,
                    "ref_no": 4,
                },
            },
            {
                "pattern": r"dear customer, payment of ([a-z \d\.,]+) has been received on your icici bank credit card account ([x\d]+) on ([a-z\d\-]+)\.thank you\.",
                "attributes": {"amount": 0, "receiver": 1, "date": 2},
            },
            {
                "pattern": r"dear customer, payment of ([a-z \d\.,]+) has been received towards your icici bank credit card ([x\d]+) on ([\da-z\-]+) through upi\. thank you\.",
                "attributes": {"amount": 0, "receiver": 1, "date": 2},
            },
            {
                "pattern": r"dear customer, account ([x\d]+) is credited with ([a-z \d\.,]+) on ([a-z\d\-]+) from ([a-z \W\d]+)\. upi ref\. no\. ([\d]+) - icici bank\.",
                "attributes": {
                    "receiver": 0,
                    "amount": 1,
                    "date": 2,
                    "sender": 3,
                    "ref_no": 4,
                },
            },
        ],
        "debit": [
            {
                "pattern": r"dear customer, icici bank fastag linked vehicle no\. ([a-z\d]+) has been debited with ([a-z\d\. ]+) on ([\d\- :]+) for toll charges with trip number ([\d]+) at [a-z\d \.]+ on ([\d\- :]+)\. avl\. bal\. is [a-z\d \-\.]+\. call [\d]+ in case of dispute\.",
                "attributes": {"amount": 1, "receiver": 0, "date": 2, "ref_no": 3},
            },
            {
                "pattern": r"icici bank acct ([x\d]+) debited for ([a-z\d \.]+) on ([a-z\d\-]+); ([a-z\d \.]+) credited\. upi:(\d+)\. call .+ for dispute\. sms block .+ to .+\.",
                "attributes": {
                    "amount": 1,
                    "sender": 0,
                    "receiver": 3,
                    "date": 2,
                    "ref_no": 4,
                },
            },
            {
                "pattern": r"icici bank acct ([x\d]+) debited (with|for) ([a-z\d\. ]+) on ([a-z\d\-]+)(\.|;|,| &) ([a-z\d\W]+) credited\. ?upi:([\d]+)\..*",
                "attributes": {
                    "amount": 2,
                    "sender": 0,
                    "receiver": 5,
                    "date": 3,
                    "ref_no": 6,
                },
            },
            {
                "pattern": r"icici bank acc ([x\d]+) debited with ([a-z\d,\. ]+) on ([a-z\d\-]+)\. info:.+\.avb bal: [a-z\d\.,]+\. for dispute\,call .+ or sms block .+ to .+",
                "attributes": {
                    "amount": 1,
                    "sender": 0,
                    "date": 2,
                },
            },
            {
                "pattern": r"dear customer, icici bank (account|acct) ([x\d]+)( is)? debited with ([a-z\d\. ,]+) on ([a-z\d\-]+)\..*",
                "attributes": {"amount": 3, "sender": 1, "date": 4},
            },
            {
                "pattern": r"dear customer, ([a-z\d\., ]+) is debited on icici bank credit card ([x\d]+) on ([a-z\d\-]+)\..+",
                "attributes": {"amount": 0, "sender": 1, "date": 2},
            },
        ],
    }

    illegal_tnx_keywords = ["requested", "will be", "delivered"]


class KotakbTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "credit": [
            {
                "pattern": r"([a-z\d\.]+) is credited in your kotak bank a\/c ([x\d]+) by upi id ([\W\w]+) on ([\-\d]+) \(upi ref no ([\d]+)\)\..+",
                "attributes": {
                    "amount": 0,
                    "receiver": 1,
                    "sender": 2,
                    "date": 3,
                    "ref_no": 4,
                },
            },
            {
                "pattern": r"thank you for (the|your) payment of ([a-z\.\d ]+) for .+ ([x\d]+) received .+ on ([a-z\d\-]+).*",
                "attributes": {"amount": 1, "receiver": 2, "date": 3},
            },
            {
                "pattern": r"([a-z\d\.]+) is credited to kotak bank a\/c no\. ([x\d]+) on ([a-z\d\-]+) as a reversal of debit transaction \(upi ref no ([\d]+)\)\..*",
                "attributes": {
                    "amount": 0,
                    "receiver": 1,
                    "date": 2,
                    "ref_no": 3,
                },
            },
            {
                "pattern": r"([a-z\d \.,]+) ?credited to a\/c ([x\d]+) ?via neft from ([a-z\d ]+) ?- utr ref ([a-z\d]+);.*",
                "attributes": {"amount": 0, "receiver": 1, "sender": 2, "ref_no": 3},
            },
            {
                "pattern": r"([a-z\d\.,]+) cr on ([a-z\d\-]+) to kotak bank ac ([x\d]+) by ac linked to mobile .+\. ?utr ?- ?([a-z\d]+)\..*",
                "attributes": {"amount": 0, "date": 1, "receiver": 2, "ref_no": 3},
            },
        ],
        "debit": [
            {
                "pattern": r"([a-z\d\.]+) is debited from kotak bank a\/c ([x\d]+) to ([\W\w]+) on ([a-z\d\-]+)\..+",
                "attributes": {"amount": 0, "sender": 1, "receiver": 2, "date": 3},
            },
            {
                "pattern": r"([a-z\d\. ,]+) is debited from kotak bank a\/c\/ credit card no. ([x\d]+) for ([a-z \d()]+) on ([a-z\d\- :]+)\. ref no: ([a-z\d]+)\..*",
                "attributes": {
                    "amount": 0,
                    "sender": 1,
                    "receiver": 2,
                    "date": 3,
                    "ref_no": 4,
                },
            },
            {
                "pattern": r"([a-z\d\., ]+) dr frm kotak bank ac ([x\d]+) to ac ([x\d]+)\. utr ?- ?([a-z\d]+)\..*",
                "attributes": {"amount": 0, "sender": 1, "receiver": 2, "ref_no": 3},
            },
            {
                "pattern": r"([a-z\d\., ]+) dr frm kotak bank ac ([x\d]+) to ([a-z\d ]+) on ([a-z\d\-]+) utr ?- ?([a-z\d]+)\..*",
                "attributes": {
                    "amount": 0,
                    "sender": 1,
                    "receiver": 2,
                    "date": 3,
                    "ref_no": 4,
                },
            },
        ],
    }

    illegal_tnx_keywords = ["requested", "will be", "delivered", "earn"]


class IndbnkTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "credit": [
            {
                "pattern": r"your a/c. ([x\d]+) is credited by ([a-z\d\. ,]+) on ([\d\-]+) by a/c linked to mobile .+ \(imps ref no. ([a-z\d]+)\)\..*",
                "attributes": {"amount": 1, "receiver": 0, "date": 2, "ref_no": 3},
            },
            {
                "pattern": r"your a\/c ([x\d]+) ? is credited by ([a-z\d\., ]+) .* as on:([\d\-\/]+).*",
                "attributes": {"receiver": 0, "amount": 1, "date": 2},
            },
        ],
        "debit": [
            {
                "pattern": r"your vpa .+ linked to indian bank a/c no\. ([x\d]+) is debited for ([a-z\d\. ,]+) and credited to ([\Wa-z\d]+) \(upi ref no ([a-z\d]+)\)\..*",
                "attributes": {"amount": 1, "sender": 0, "receiver": 2, "ref_no": 3},
            },
            {
                "pattern": r"([a-z\d\., ]+) spent on .+ using .+ on ([\d\/ :]+) at ([a-z \d\W]+) from ac:([x\d]+)\..*",
                "attributes": {"amount": 0, "date": 1, "receiver": 2, "sender": 3},
            },
        ],
    }

    debit_keywords = TransactionSMSDecoder.debit_keywords + ["spent on"]


class SBIInbTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "credit": [
            {
                "pattern": r"dear customer, your a\/c no\. ([x\d]+) is credited by ([a-z\.\d ,]+) on ([\d\-]+) by a/c linked to mobile .+ ?- ?([a-z \d]+) ?\(imps ref no ([\d]+)\)\..*",
                "attributes": {
                    "amount": 1,
                    "receiver": 0,
                    "sender": 3,
                    "date": 2,
                    "ref_no": 4,
                },
            }
        ]
    }


class AtmSBITransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "debit": [
            {
                "pattern": r"dear sbi customer, ([a-z\d\. ,]+) withdrawn at .+ from a/c ?([x\d]+) on ([a-z\d\-\/]+) transaction number ([a-z\d]+)\..*",
                "attributes": {
                    "amount": 0,
                    "sender": 1,
                    "date": 2,
                    "ref_no": 3,
                },
            },
            {
                "pattern": r"dear customer, transaction number ([a-z\d]+) for ([a-z\d\., ]+) by sbi debit card ([x\d]+)( done)? at .+ on ([a-z\d]+).*",
                "attributes": {"ref_no": 0, "amount": 1, "sender": 2, "date": 4},
            },
        ]
    }

    legal_tnx_keywords = TransactionSMSDecoder.legal_tnx_keywords + [
        "dear customer, transaction number"
    ]

    debit_keywords = TransactionSMSDecoder.debit_keywords + [
        "dear customer, transaction number"
    ]


class SPRCRDTransactionSMSDecoder(TransactionSMSDecoder):
    pass


class SBIDGTTransactionSMSDecoder(TransactionSMSDecoder):
    pass


class AxisBkTransactionSMSDecoder(TransactionSMSDecoder):
    illegal_tnx_keywords = ["requested"]


class RBISayTransactionSMSDecoder(TransactionSMSDecoder):
    illegal_tnx_keywords = ["failed digital transaction"]


class HDFCBkTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "credit": [
            {
                "pattern": r"update: your a\/c ([x\d]+) credited with ([a-z\d \.,]+) on ([\d\-\/a-z]+) by a/c linked to mobile no .+ \(imps ref no. ([a-z\d]+)\).*",
                "attributes": {"receiver": 0, "amount": 1, "date": 2, "ref_no": 3},
            },
            {
                "pattern": r"update(:|!) ([a-z\d \.,]+) deposited in( hdfc bank)? a\/c ([x\d]+) on ([\d\-\/a-z]+) for .*",
                "attributes": {"amount": 1, "receiver": 3, "date": 4},
            },
            {
                "pattern": r"hdfc bank: ([a-z \d\.,]+) credited to a\/c ([x\*\d]+) on ([a-z\d\- :]+) by a\/c linked to vpa ([a-z\W\d ]+) \(upi ref no  ([\d]+)\)\.",
                "attributes": {
                    "amount": 0,
                    "receiver": 1,
                    "date": 2,
                    "sender": 3,
                    "ref_no": 4,
                },
            },
            {
                "pattern": r"alert: a\/c ([x\d]+) credited with ([a-z \d\.,]+) on ([a-z\d\/\.]+) at .*",
                "attributes": {"amount": 1, "receiver": 0, "date": 2},
            },
            {
                "pattern": r"received  *hdfc bank upi payment:([a-z\d\., ]+) from ([a-z\W \d]+) on ([\d:\- \/]+)\|transaction id:([\d]+)\..*",
                "attributes": {"amount": 0, "sender": 1, "date": 2, "ref_no": 3},
            },
        ],
        "debit": [
            {
                "pattern": r"hdfc bank: ([a-z \d\.,]+) debited from a\/c ([x\*\d]+) on ([\d\-\/a-z]+) to (vpa|a\/c) ([a-z\W\d\* ]+) ?\(upi ref no\.? ([\d]+)\)\..*",
                "attributes": {
                    "amount": 0,
                    "sender": 1,
                    "receiver": 4,
                    "date": 2,
                    "ref_no": 5,
                },
            },
            {
                "pattern": r"update: ([a-z\d\., ]+) debited from hdfc bank ([x\d]+) on ([a-z\d\-\/]+)\..*",
                "attributes": {"amount": 0, "sender": 1, "date": 2},
            },
            {
                "pattern": r"update: ([a-z ,\.\d]+) debited from a\/c ([x\d]+) on ([a-z\d\-\/]+)\..*",
                "attributes": {"amount": 0, "sender": 1, "date": 2},
            },
            {
                "pattern": r"alert:you've withdrawn ([a-z\d\., ]+) via debit card ([x\d]+) at ([a-z\W\d ]+) on ([\d\-:]+)\..*",
                "attributes": {"amount": 0, "sender": 1, "receiver": 2, "date": 3},
            },
            {
                "pattern": r"([a-z\d\., ]+) debited from a\/c ([x\*\d]+) on ([\d\-\/]+) to vpa ([a-z\W\d ]+) ?\(upi ref no\.? ([\d]+)\)\..*",
                "attributes": {
                    "amount": 0,
                    "sender": 1,
                    "date": 2,
                    "receiver": 3,
                    "ref_no": 4,
                },
            },
        ],
    }

    illegal_tnx_keywords = TransactionSMSDecoder.illegal_tnx_keywords + [
        "request",
        "delivered",
    ]


class SBYONOTransactionSMSDecoder(TransactionSMSDecoder):
    pass


class HDFCBNTransactionSMSDecoder(TransactionSMSDecoder):
    illegal_tnx_keywords = TransactionSMSDecoder.illegal_tnx_keywords + [
        "interest rate"
    ]


class SBIUpiTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "debit": [
            {
                "pattern": r"([a-z\d\., ]+) debited(@|!)sbi upi frm a\/c ?([x\d]+) on ([a-z\d]+) ref no ([\d]+)\..*",
                "attributes": {"amount": 0, "sender": 2, "date": 3, "ref_no": 4},
            },
            {
                "pattern": r".*a\/c ([x\d]+).*debited by ([a-z\d\., ]+) on( date)? ([a-z\d]+) transfer to ([a-z\d\W ]+) ref no ([\d]+)\..*",
                "attributes": {
                    "sender": 0,
                    "amount": 1,
                    "date": 3,
                    "receiver": 4,
                    "ref_no": 5,
                },
            },
        ],
        "credit": [
            {
                "pattern": r"dear sbi upi user, your a\/c ?([x\d]+) credited (by|with) ([a-z\d\., ]+) on ([a-z\d]+) .*\(ref no ([\d]+)\)",
                "attributes": {"receiver": 0, "amount": 2, "date": 3, "ref_no": 4},
            }
        ],
    }


class SBIPsgTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "credit": [
            {
                "pattern": r"dear customer, ([a-z \d\.,]+) credited to your a\/c no ([x\d]+) on ([\d\/]+).*",
                "attributes": {"amount": 0, "receiver": 1, "date": 2},
            }
        ]
    }

    illegal_tnx_keywords = TransactionSMSDecoder.illegal_tnx_keywords + [
        "avail bal in a/c"
    ]


class CBSSBITransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "credit": [
            {
                "pattern": r"your a\/?c ([x\d]+) credited ([a-z\d\., ]+) on ([\d\/]+).*",
                "attributes": {"receiver": 0, "amount": 1, "date": 2},
            },
            {
                "pattern": r"dear customer, .+ of ([a-z\d\., ]+) has been credited to your a\/?c no\. ?([x\d]+) on ([\d\/]+).*",
                "attributes": {"amount": 0, "receiver": 1, "date": 2},
            },
        ],
        "debit": [
            {
                "pattern": r"your a\/?c ([x\d]+) debited ([a-z\d\., ]+) on ([\d\/]+).*",
                "attributes": {"sender": 0, "amount": 1, "date": 2},
            },
            {
                "pattern": r".*a\/c ([x\d]+) has a debit by (.+) of ([a-z\d,\. ]+) on ([\d\/]+)\..*",
                "attributes": {"sender": 0, "receiver": 1, "amount": 2, "date": 3},
            },
        ],
    }

    illegal_tnx_keywords = TransactionSMSDecoder.illegal_tnx_keywords + ["request"]
    legal_tnx_keywords = TransactionSMSDecoder.legal_tnx_keywords + ["debit"]
    debit_keywords = TransactionSMSDecoder.debit_keywords + ["debit"]


class HDFCLITransactionSMSDecoder(TransactionSMSDecoder):
    debit_keywords = TransactionSMSDecoder.debit_keywords + ["we have received"]

    patterns = {
        "debit": [
            {
                "pattern": r"thank you! we have received your payment of ([a-z\d\., ]+) for .+ on ([\d\/]+).*",
                "attributes": {"amount": 0, "date": 1},
            }
        ]
    }


class SBIOtpTransactionSMSDecoder(TransactionSMSDecoder):
    pass


class PSBankTransactionSMSDecoder(TransactionSMSDecoder):
    patterns = {
        "debit": [
            {
                "pattern": r"([a-z \d\.,]+) debited from a\/c ([\*x\d]+).*([\d\- :]+)\..*",
                "attributes": {"amount": 0, "sender": 1, "date": 2},
            },
            {
                "pattern": r".*a\/c no ([\*x\d]+) debited *.*with ([a-z \d\.,]+)--.*\(([\d\- :]+)\).*",
                "attributes": {
                    "receiver": 0,
                    "amount": 1,
                    "date": 2,
                },
            },
            {
                "pattern": r"rtgs transaction with reference number ([a-z\d]+) for ([a-z\d\., ]+) *has been credited on ([a-z\d:\-]+) *to beneficiary.*",
                "attributes": {"ref_no": 0, "amount": 1, "date": 2},
            },
            {
                "pattern": r".*vpa ([a-z\d\W ]+) linked to .* a\/c no\. ([x\d]+) is debited for ([a-z\d\., ]+) and credited to ([a-z\d\W ]+) \(upi ref no ([\d]+)\).*",
                "attributes": {"sender": 1, "amount": 2, "receiver": 3, "ref_no": 4},
            },
            {
                "pattern": r"your a\/c no\. ([a-z\d]+) is debited for ([a-z\d\., ]+) on ([\d\-]+) and credited to a\/c no\. ([a-z\d]+) \(upi ref no ([\d]+)\).*",
                "attributes": {
                    "sender": 0,
                    "amount": 1,
                    "date": 2,
                    "receiver": 3,
                    "ref_no": 4,
                },
            },
        ],
        "credit": [
            {
                "pattern": r".*a\/c no ([\*x\d]+) credited with ([a-z \d\.,]+)--.*\(([\d\- :]+)\).*",
                "attributes": {
                    "receiver": 0,
                    "amount": 1,
                    "date": 2,
                },
            }
        ],
    }

    illegal_tnx_keywords = TransactionSMSDecoder.illegal_tnx_keywords + ["will be"]
    debit_keywords = TransactionSMSDecoder.debit_keywords + ["rtgs transaction"]


class AIRBnkTransactionSMSDecoder(TransactionSMSDecoder):
    illegal_tnx_keywords = TransactionSMSDecoder.illegal_tnx_keywords + ["registering"]
    debit_keywords = TransactionSMSDecoder.debit_keywords + ["to company"]

    patterns = {
        "debit": [
            {
                "pattern": r".*charge of ([a-z\d\., ]+) .* for .* has been debited from your savings a\/c ([a-z\d]+).*",
                "attributes": {"amount": 0, "sender": 1},
            },
            {
                "pattern": r"hello! you have successfully deposited \? ([\d\.]+).*txn id # ([a-z\d]+) on ([a-z\d\- :]+)\..*",
                "attributes": {"amount": 0, "ref_no": 1, "date": 2},
            },
        ],
    }


class UnionbTransactionSMSDecoder(TransactionSMSDecoder):
    illegal_tnx_keywords = TransactionSMSDecoder.illegal_tnx_keywords + ["otp"]
    patterns = {
        "credit": [
            {
                "pattern": r".*a\/c ([\*x\d]+) credited for ([a-z\d:,\. ]+) on ([\d\- :]+) .* ref no ([\d]+).*",
                "attributes": {"receiver": 0, "amount": 1, "date": 2, "ref_no": 3},
            },
            {
                "pattern": r".*a\/c ([\*x\d]+).* credited for ([a-z\d:,\. ]+) on ([\d\- :]+).*",
                "attributes": {"receiver": 0, "amount": 1, "date": 2},
            },
        ],
        "debit": [
            {
                "pattern": r".*a\/c ([\*x\d]+) debited for ([a-z\d:,\. ]+) on ([\d\- :]+) by .* ref no ([\d]+).*",
                "attributes": {"sender": 0, "amount": 1, "date": 2, "ref_no": 3},
            },
            {
                "pattern": r".*a\/c ([\*x\d]+) debited for ([a-z\d:,\. ]+) on ([\d\- :]+).*",
                "attributes": {"sender": 0, "amount": 1, "date": 2},
            },
            {
                "pattern": r".*a\/c no. ([\*x\d]+) is debited for ([a-z\d:,\. ]+) on ([\d\- :,a-z]+) \(upi ref no ([\d]+)\).*",
                "attributes": {"sender": 0, "amount": 1, "date": 2, "ref_no": 3},
            },
        ],
    }


class IDFCFbTransactionSMSDecoder(TransactionSMSDecoder):
    debit_keywords = TransactionSMSDecoder.debit_keywords + ["towards your loan"]
    illegal_tnx_keywords = TransactionSMSDecoder.illegal_tnx_keywords + [
        "start a new income stream",
        "will be",
    ]

    patterns = {
        "debit": [
            {
                "pattern": r"received ([a-z\d\. ,]+) by cash on ([\d\/]+) vide ereceipt number ([a-z\d]+) towards your loan a\/c no\. ([x\d]+)\..*",
                "attributes": {"amount": 0, "date": 1, "ref_no": 2, "receiver": 3},
            }
        ]
    }


class ICIBnkTransactionSMSDecoder(TransactionSMSDecoder):
    pass


class AXISMRTranasctionSMSDecoder(TransactionSMSDecoder):
    pass


class SBICmpTransactionSMSDecoder(TransactionSMSDecoder):
    pass


class SBGMBSTransactionSMSDecoder(TransactionSMSDecoder):
    pass


class PNBSmsTransactionSMSDecoder(TransactionSMSDecoder):
    pass


decoders: Dict[str, TransactionSMSDecoder] = {
    "paytmb": PaytmTransactionSMSDecoder(),
    "icicib": IcicibTransactionSMSDecoder(),
    "kotakb": KotakbTransactionSMSDecoder(),
    "indbnk": IndbnkTransactionSMSDecoder(),
    "sbiinb": SBIInbTransactionSMSDecoder(),
    "atmsbi": AtmSBITransactionSMSDecoder(),
    "sprcrd": SPRCRDTransactionSMSDecoder(),
    "sbidgt": SBIDGTTransactionSMSDecoder(),
    "axisbk": AxisBkTransactionSMSDecoder(),
    "rbisay": RBISayTransactionSMSDecoder(),
    "hdfcbk": HDFCBkTransactionSMSDecoder(),
    "sbyono": SBYONOTransactionSMSDecoder(),
    "hdfcbn": HDFCBNTransactionSMSDecoder(),
    "sbiupi": SBIUpiTransactionSMSDecoder(),
    "sbipsg": SBIPsgTransactionSMSDecoder(),
    "cbssbi": CBSSBITransactionSMSDecoder(),
    "hdfcli": HDFCLITransactionSMSDecoder(),
    "sbiotp": SBIOtpTransactionSMSDecoder(),
    "psbank": PSBankTransactionSMSDecoder(),
    "airbnk": AIRBnkTransactionSMSDecoder(),
    "unionb": UnionbTransactionSMSDecoder(),
    "idfcfb": IDFCFbTransactionSMSDecoder(),
    "icibnk": ICIBnkTransactionSMSDecoder(),
    "axismr": AXISMRTranasctionSMSDecoder(),
    "sbicmp": SBICmpTransactionSMSDecoder(),
    "sbgmbs": SBGMBSTransactionSMSDecoder(),
    "pnbsms": PNBSmsTransactionSMSDecoder(),
}


def decode_smses(smses: List[SMS]):
    attributes = ("tnx_type", "sender", "receiver", "date", "ref_no", "amount")
    n = len(smses)
    for i, sms in enumerate(smses):
        if sms.address not in decoders:
            print(
                f"[{i + 1}/{n} - {(i + 1) * 100 / n:.2f}%] decoder not available for the address {sms.address}"
            )
            return

        decoder = decoders[sms.address]
        data = decoder.decode(sms)
        if data is NotImplemented:
            print(
                f"[{i + 1}/{n} - {(i + 1) * 100 / n:.2f}%] {decoder.__class__.__name__} is not implemented"
            )
            return

        if TransactionSMSDecoder.SMS_TYPE_FIELD not in data:
            print(
                f"[{i + 1}/{n} - {(i + 1) * 100 / n:.2f}%] failed to classify sms {sms}"
            )
            return

        if data[TransactionSMSDecoder.SMS_TYPE_FIELD] is True:
            for attrib in attributes:
                if attrib not in data:
                    print(data)
                    print(
                        f"[{i + 1}/{n} - {(i + 1) * 100 / n:.2f}%] decoder didn't return any value for the attribute '{attrib}' for the sms {sms}"
                    )
                    return

            if data[TransactionSMSDecoder.SMS_TYPE_FIELD] == "unknown":
                print(data)
                print(
                    f"[{i + 1}/{n} - {(i + 1) * 100 / n:.2f}%] decoder returned 'unknown' transaction type for {sms}"
                )
                return

        print(f"[{i + 1}/{n} - {(i + 1) * 100 / n:.2f}%] done\r", end="")


def preprocess(s: str) -> str:
    return (
        s.lower()
        .replace("\n", " ")
        .replace(" ur ", " your ")
        .replace(" trf ", " transfer ")
        .replace(" refno ", " ref no ")
    )


def main():
    with open("data/filtered_bank_sms.json", "r") as fp:
        smses = [
            SMS(row["address"].lower(), preprocess(row["body"]))
            for row in json.load(fp)
        ]
        decode_smses(smses)


if __name__ == "__main__":
    main()
