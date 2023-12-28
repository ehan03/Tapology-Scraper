# standard library imports

# local imports

# third party imports
from scrapy import Field, Item


class TapologyBoutItem(Item):
    """
    Item class for bout data from Tapology
    """

    BOUT_ID = Field()
    UFCSTATS_BOUT_ID = Field()
    EVENT_ID = Field()
    UFCSTATS_EVENT_ID = Field()
    EVENT_NAME = Field()
    DATE = Field()
    REGION = Field()
    LOCATION = Field()
    VENUE = Field()
    BOUT_ORDINAL = Field()
    BOUT_CARD_TYPE = Field()

    # Fighter info
    FIGHTER_1_ID = Field()
    FIGHTER_2_ID = Field()
    FIGHTER_1_RECORD_AT_BOUT = Field()
    FIGHTER_2_RECORD_AT_BOUT = Field()
    FIGHTER_1_WEIGHT_POUNDS = Field()
    FIGHTER_2_WEIGHT_POUNDS = Field()
    FIGHTER_1_GYM = Field()
    FIGHTER_2_GYM = Field()


class TapologyFighterItem(Item):
    """
    Item class for fighter data from Tapology
    """

    FIGHTER_ID = Field()
    UFCSTATS_FIGHTER_ID = Field()
    SHERDOG_FIGHTER_ID = Field()
    FIGHTER_NAME = Field()
    NATIONALITY = Field()
    HEIGHT_INCHES = Field()
    REACH_INCHES = Field()
    DATE_OF_BIRTH = Field()
