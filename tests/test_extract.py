"""Extraction tests — messy real-world input shapes."""
from server.extract import (extract_all, extract_accounts, extract_claimed_category,
                            extract_org_names, extract_phones, extract_regnos,
                            extract_upi, extract_upi_links, normalize)


def test_upi_basic_and_dotted_username():
    assert extract_upi("pay to taurus.cf.brk@validaxis now") == ["taurus.cf.brk@validaxis"]
    assert extract_upi("abc.brk@validhdfc") == ["abc.brk@validhdfc"]


def test_email_not_upi():
    assert extract_upi("mail social@zerodha.com or support@groww.in") == []


def test_at_obfuscation():
    assert extract_all("pay zerodha.brk(at)validhdfc today")["upis"] == ["zerodha.brk@validhdfc"]
    assert extract_all("send to groww.mf[at]validicici")["upis"] == ["groww.mf@validicici"]
    # bare " at " with dotted username → handle
    assert extract_all("pay zerodha.brk at validhdfc")["upis"] == ["zerodha.brk@validhdfc"]
    # guarded: plain english "at" must not create handles
    assert extract_all("invest at hdfc branch")["upis"] == []
    assert extract_all("meet at mumbai station")["upis"] == []
    # "at valid…" is handle-shaped intent (nobody says 'at validhdfc' casually)
    assert extract_all("pay money at validhdfc to abc")["upis"] == ["money@validhdfc"]


def test_zero_width_evasion():
    assert extract_all("pay scam\u200b99@ybl")["upis"] == ["scam99@ybl"]


def test_ocr_space_around_at():
    """Tesseract inserts a space around '@' at chat-screenshot glyph sizes.

    Found from a real device report: a friend's WhatsApp screenshot came back
    from OCR as "jaiswalrahul2427-1 @oksbi" and the app answered "no payment
    details found", even though the handle was sitting right there in the text.
    _UPI requires the two halves to be adjacent, so a single space hid it
    completely. Reproduced at 28px and 36px glyphs; clean at 44px and above,
    which is why it passed every earlier test and only failed in the field.
    """
    # the exact shape observed on the device
    assert extract_all("Pay to UPI ID:\njaiswalrahul2427-1 @oksbi")["upis"] == [
        "jaiswalrahul2427-1@oksbi"]
    # space before, after, or both; tab as well
    assert extract_all("scam99 @ybl")["upis"] == ["scam99@ybl"]
    assert extract_all("scam99@ ybl")["upis"] == ["scam99@ybl"]
    assert extract_all("scam99 @ ybl")["upis"] == ["scam99@ybl"]
    assert extract_all("scam99\t@ybl")["upis"] == ["scam99@ybl"]
    # dotted @valid handles survive the same treatment
    assert extract_all("pay taurus.cf.brk @validaxis")["upis"] == ["taurus.cf.brk@validaxis"]
    # a long plain username qualifies on length alone
    assert extract_all("rahulinvestments @paytm")["upis"] == ["rahulinvestments@paytm"]
    # and the adjacent form is untouched
    assert extract_all("scam99@ybl")["upis"] == ["scam99@ybl"]


def test_ocr_space_guards_reject_prose():
    """Rejoining must not manufacture a payment destination out of a sentence.

    The two errors are not symmetric: a missed handle yields an honest "nothing
    to check", while an invented one is sent to SEBI Check, comes back invalid,
    and shows the user a RED FLAG for prose that was never a payee. So the PSP
    must start with a letter and the username must carry a digit, dot or dash or
    be at least 8 characters.
    """
    assert extract_all("meet @ 5pm")["upis"] == []            # PSP starts with a digit
    assert extract_all("offer valid @ 2024")["upis"] == []     # PSP starts with a digit
    assert extract_all("pay @ oksbi")["upis"] == []            # short plain username
    assert extract_all("contact @ support")["upis"] == []      # short plain username
    assert extract_all("invest @ zerodha office")["upis"] == []
    # An email stays an email: the dot in the domain is what separates the two,
    # and that rule must survive the space-rejoining above.
    assert extract_all("email me @ gmail.com")["upis"] == []
    assert extract_all("reach us @ support@groww.in")["upis"] == []


def test_upi_deep_link():
    links = extract_upi_links("scan: upi://pay?pa=fraud99@ybl&pn=Quick%20Money&am=50000&cu=INR")
    assert links[0]["pa"] == "fraud99@ybl"
    assert links[0]["pn"] == "Quick Money"
    assert links[0]["am"] == "50000"
    # deep-link handle also lands in upis
    assert "fraud99@ybl" in extract_all("upi://pay?pa=fraud99@ybl&cu=INR")["upis"]


def test_ifsc():
    assert extract_all("NEFT to HDFC0001234 / SBIN0005322")["ifscs"] == ["HDFC0001234", "SBIN0005322"]


def test_account_vs_phone_disambiguation():
    text = "A/C No 50100234567890 IFSC HDFC0001234, call 9876543210"
    r = extract_all(text)
    assert "50100234567890" in r["accounts"]
    assert "9876543210" in r["phones"]
    assert "9876543210" not in r["accounts"]


def test_account_hindi_keywords():
    r = extract_all("मेरे खाता में 123456789012 पैसे ट्रांसफर करें, बैंक IFSC SBIN0005322")
    assert "123456789012" in r["accounts"]


def test_regno_formats():
    assert "INZ000031633" in extract_regnos("Reg No INZ000031633")
    assert "INA000012345" in extract_regnos("SEBI Registration INA000012345")
    # loose pattern needs digits — "SEBI registered advisor" must not yield noise
    assert extract_regnos("SEBI registered advisor here") == []


def test_org_names():
    names = extract_org_names("I am Rohit from Rakesh Capital Securities, SEBI approved")
    assert any("Rakesh Capital Securities" in n for n in names)


def test_claimed_category():
    assert extract_claimed_category("we are a registered mutual fund, start SIP") == "mf"
    assert extract_claimed_category("open demat with India's best stock broker") == "brk"
    assert extract_claimed_category("SEBI registered investment advisor") == "ia"
    # ambiguous → None
    assert extract_claimed_category("mutual fund SIP and stock broker account") is None
    assert extract_claimed_category("hello friend") is None


def test_amounts():
    assert extract_all("pay ₹50,000 today")["amounts"] == ["₹50,000"]
    assert extract_all("send Rs 2.5 lakh")["amounts"] == ["Rs 2.5 lakh"]


def test_full_scam_message():
    msg = ("🚀 VIP tips group join karo! SEBI registered advisor Groww Investments "
           "(Reg INZ000031633). Guaranteed 30% monthly! Pay ₹25,000 to "
           "groww.brk(at)validhdfc. Withdrawal blocked? Unlock fee bharo. "
           "A/C 50100123456789 IFSC HDFC0001234. Call 9812345678.")
    r = extract_all(msg)
    assert "groww.brk@validhdfc" in r["upis"]
    assert "INZ000031633" in r["regnos"]
    assert "50100123456789" in r["accounts"]
    assert "HDFC0001234" in r["ifscs"]
    assert "9812345678" in r["phones"]
    assert r["claimed_category"] == "ia"  # "SEBI registered advisor" claim
    assert any("Groww Investments" in n for n in r["org_names"])
