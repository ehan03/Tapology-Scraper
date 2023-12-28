# standard library imports
from typing import Optional

# local imports

# third party imports


def convert_height(height: str) -> Optional[float]:
    """
    Converts a height string to inches
    """

    if height != "--":
        feet, inches = height.split()
        return 12.0 * float(feet[:-1]) + float(inches[:-1])
    else:
        return None
