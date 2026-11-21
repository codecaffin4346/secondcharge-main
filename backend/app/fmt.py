def inr(v: float, symbol: str = "₹") -> str:
    """Indian digit grouping: 1234567 -> ₹12,34,567."""
    neg = v < 0
    s = str(int(round(abs(v))))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return ("-" if neg else "") + symbol + s
