from datetime import datetime


def tag_season(pulled_at: datetime) -> str:
    """
    Tag an ad pull date with a Pakistani e-commerce season.
    
    Returns one of:
      - ramzan (March-April)
      - eid_ul_fitr (April-May)
      - eid_ul_adha (June-July)
      - independence_day (August)
      - winter_sale (November-January)
      - regular (everything else)
    """
    if pulled_at is None:
        return "regular"

    month = pulled_at.month

    if month in (3, 4):
        return "ramzan"
    if month in (4, 5):
        return "eid_ul_fitr"
    if month in (6, 7):
        return "eid_ul_adha"
    if month == 8:
        return "independence_day"
    if month in (11, 12, 1):
        return "winter_sale"

    return "regular"
