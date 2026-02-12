def roe(net_income: float, total_equity: float) -> float | None:
    if total_equity is None or total_equity == 0:
        return None
    return net_income / total_equity


def operating_margin(operating_income: float, revenue: float) -> float | None:
    if revenue is None or revenue == 0:
        return None
    return operating_income / revenue
