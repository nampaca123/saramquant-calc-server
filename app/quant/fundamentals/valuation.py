def eps(net_income: float, shares: int) -> float | None:
    if not shares or shares <= 0:
        return None
    return net_income / shares


def bps(total_equity: float, shares: int) -> float | None:
    if not shares or shares <= 0:
        return None
    return total_equity / shares


def per(price: float, eps_val: float) -> float | None:
    if eps_val is None or eps_val == 0:
        return None
    return price / eps_val


def pbr(price: float, bps_val: float) -> float | None:
    if bps_val is None or bps_val <= 0:
        return None
    return price / bps_val
