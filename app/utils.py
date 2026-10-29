def normalize_phone(phone: str) -> str:
    """
    +9779801122334 -> 9801122334
    9779801122334  -> 9801122334
    9801122334     -> 9801122334
    Raises ValueError if invalid.
    """
    phone = phone.strip().replace(" ", "").replace("-", "")

    if phone.startswith("+977"):
        phone = phone[4:]
    elif phone.startswith("977"):
        phone = phone[3:]

    if len(phone) != 10:
        raise ValueError(f"Invalid phone (not 10 digits): {phone}")
    if not phone.startswith(("97", "98")):
        raise ValueError(f"Invalid phone (must start with 97 or 98): {phone}")

    return phone


def count_parts(message: str) -> int:
    """
    GSM-7: 1 part up to 160 chars, then parts of 153.
    Unicode (any char > 127): 1 part up to 70 chars, then parts of 67.
    """
    is_unicode = any(ord(ch) > 127 for ch in message)
    length = len(message)

    if is_unicode:
        return 1 if length <= 70 else (length + 66) // 67
    else:
        return 1 if length <= 160 else (length + 152) // 153