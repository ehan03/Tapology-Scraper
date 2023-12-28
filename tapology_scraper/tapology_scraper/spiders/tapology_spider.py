# standard library imports
import re
from ast import literal_eval
from html import unescape

# third party imports
import pandas as pd
import w3lib.html
from scrapy.http import FormRequest
from scrapy.spiders import Spider

# local imports
from ..items import (
    TapologyBoutItem,
    TapologyFighterItem,
)
from ..utils import (
    convert_height,
)


class TapologySpider(Spider):
    """
    Spider for scraping UFC bout and fighter data from Tapology
    """

    name = "tapology_spider"
    allowed_domains = ["tapology.com"]
    start_urls = [
        "https://www.tapology.com/fightcenter?group=ufc&schedule=results&sport=mma"
    ]
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 10,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_TIMEOUT": 600,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            "scrapy_user_agents.middlewares.RandomUserAgentMiddleware": 400,
        },
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "FEED_EXPORT_ENCODING": "utf-8",
        "DEPTH_PRIORITY": 1,
        "SCHEDULER_DISK_QUEUE": "scrapy.squeues.PickleFifoDiskQueue",
        "SCHEDULER_MEMORY_QUEUE": "scrapy.squeues.FifoMemoryQueue",
        "RETRY_TIMES": 1,
        "LOG_LEVEL": "INFO",
        "ITEM_PIPELINES": {
            # If you choose to handle the items in a particular way as user-specified
            # in pipelines.py, make sure to uncomment the two lines below
            # "tapology_scraper.pipelines.TapologyBoutsPipeline": 100,
            # "tapology_scraper.pipelines.TapologyFightersPipeline": 200,
        },
        "CLOSESPIDER_ERRORCOUNT": 1,
    }

    def __init__(self, *args, scrape_type, **kwargs):
        super().__init__(*args, **kwargs)
        assert scrape_type in {"most_recent", "all"}
        self.scrape_type = scrape_type

    def parse(self, response):
        event_listings = response.css("section.fcListing > div.main > div.left")
        event_urls = []
        for event_listing in event_listings:
            event_urls.append(
                response.urljoin(
                    event_listing.css("div.promotion > span.name > a::attr(href)").get()
                )
            )

        if self.scrape_type == "all":
            for event_url in event_urls:
                yield response.follow(
                    event_url,
                    callback=self.parse_event,
                )

            # Workaround for terrible Ajax pagination, part 1
            pagination_headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Accept": """*/*;q=0.5, text/javascript, application/javascript,
                            application/ecmascript, application/x-ecmascript""",
            }
            next_page = response.css("span.next > a::attr(href)")
            next_page_url = [response.urljoin(url.get()) for url in next_page]
            if next_page_url:
                yield FormRequest(
                    url=next_page_url[0],
                    method="GET",
                    headers=pagination_headers,
                    callback=self.parse_next_page,
                )
        else:
            yield response.follow(
                event_urls[0],
                callback=self.parse_event,
            )

    def parse_next_page(self, response):
        # Workaround, part 2
        data = response.text
        data = re.search(r"html\((.*)\);", data)
        assert data is not None
        data = data.group(1)  # type: ignore
        data = unescape(literal_eval(data)).replace(r"\/", "/")

        yield from self.parse(response.replace(body=data))  # type: ignore

    def parse_event(self, response):
        bouts = response.css(
            "div.fightCardMatchup > table > tr > td > span.billing > a::attr(href)"
        )
        bout_urls = [response.urljoin(url.get()) for url in bouts]

        event_id = response.url.split("/")[-1]
        event_name = response.css("div.eventPageHeaderTitles > h1::text").get().strip()
        event_info_list = [
            w3lib.html.remove_tags(x).strip()
            for x in response.css(
                "div.details.details_with_poster.clearfix > div.right > ul.clearfix > li"
            ).getall()
        ]
        region = response.css(
            "div.regionFCSidebar > div.iconLead > div.textContents > div.leader > a::text"
        ).get()

        date = location = venue = None
        for i, info in enumerate(event_info_list):
            if i == 0:
                raw_date = info.split(" ")[1]
                date = pd.to_datetime(raw_date).strftime("%Y-%m-%d")
            elif info.startswith("Location:"):
                location_raw = info.replace("Location:", "").strip()
                if location_raw:
                    location = location_raw
            elif info.startswith("Venue:"):
                venue_raw = info.replace("Venue:", "").strip()
                if venue_raw:
                    venue = venue_raw

        event_and_promo_links = response.css(
            "div.details.details_with_poster.clearfix > div.right > ul.clearfix > li > div.externalIconsHolder > a::attr(href)"
        ).getall()
        ufcstats_event_id = None
        for link in event_and_promo_links:
            if "www.ufcstats.com/event-details/" in link:
                ufcstats_event_id = link.split("/")[-1]
                break
        assert ufcstats_event_id is not None

        for bout_ordinal, bout_url in enumerate(reversed(bout_urls)):
            yield response.follow(
                bout_url,
                callback=self.parse_bout,
                cb_kwargs={
                    "event_id": event_id,
                    "ufcstats_event_id": ufcstats_event_id,
                    "event_name": event_name,
                    "date": date,
                    "region": region,
                    "location": location,
                    "venue": venue,
                    "bout_ordinal": bout_ordinal,
                },
            )

    def parse_bout(
        self,
        response,
        event_id,
        ufcstats_event_id,
        event_name,
        date,
        region,
        location,
        venue,
        bout_ordinal,
    ):
        bout_item = TapologyBoutItem()
        bout_id = response.url.split("/")[-1]

        bout_item["BOUT_ID"] = bout_id
        bout_item["EVENT_ID"] = event_id
        bout_item["EVENT_NAME"] = event_name
        bout_item["DATE"] = date
        bout_item["REGION"] = region
        bout_item["LOCATION"] = location
        bout_item["VENUE"] = venue
        bout_item["BOUT_ORDINAL"] = bout_ordinal

        bout_item["UFCSTATS_EVENT_ID"] = ufcstats_event_id

        bout_and_event_links = response.css(
            "div.details.details_with_poster.clearfix > div.right > ul.clearfix > li > div.externalIconsHolder > a::attr(href)"
        ).getall()
        ufcstats_bout_id = None
        for link in bout_and_event_links:
            if link.startswith("http://www.ufcstats.com/fight-details/"):
                ufcstats_bout_id = link.split("/")[-1]
                break
        assert ufcstats_bout_id is not None

        bout_item["UFCSTATS_BOUT_ID"] = ufcstats_bout_id

        bout_preresult = (
            response.css("h4.boutPreResult::text").get().split(" | ")[0].strip()
        )
        if bout_preresult == "Preliminary Card":
            bout_item["BOUT_CARD_TYPE"] = "Prelim"
        else:
            bout_item["BOUT_CARD_TYPE"] = "Main"

        # Fighter info
        f1_url = response.css("span.fName.left > a::attr(href)").get()
        f2_url = response.css("span.fName.right > a::attr(href)").get()

        bout_item["FIGHTER_1_ID"] = f1_url.split("/")[-1]
        bout_item["FIGHTER_2_ID"] = f2_url.split("/")[-1]

        stats_table_rows = response.css("table.fighterStats.spaced > tr")
        for row in stats_table_rows:
            values = row.css("td").getall()
            assert len(values) == 5
            f1_stat = w3lib.html.remove_tags(values[0]).strip()
            stat_category = w3lib.html.remove_tags(values[2]).strip()
            f2_stat = w3lib.html.remove_tags(values[4]).strip()

            if stat_category == "Pro Record At Fight":
                bout_item["FIGHTER_1_RECORD_AT_BOUT"] = f1_stat if f1_stat else None
                bout_item["FIGHTER_2_RECORD_AT_BOUT"] = f2_stat if f2_stat else None
            elif stat_category == "Weigh-In Result":
                bout_item["FIGHTER_1_WEIGHT_POUNDS"] = (
                    float(f1_stat.split(" ")[0])
                    if (f1_stat and f1_stat != "N/A")
                    else None
                )
                bout_item["FIGHTER_2_WEIGHT_POUNDS"] = (
                    float(f2_stat.split(" ")[0])
                    if (f2_stat and f2_stat != "N/A")
                    else None
                )
            elif stat_category == "Gym":
                if f1_stat:
                    f1_gym_list = f1_stat.split("\n\n")
                    if len(f1_gym_list) > 1:
                        f1_possible_gyms = []
                        f1_flag = False
                        for f1_gym in f1_gym_list:
                            if "(Primary)" in f1_gym:
                                bout_item["FIGHTER_1_GYM"] = f1_gym.replace(
                                    "(Primary)", ""
                                ).strip()
                                f1_flag = True
                                break

                            if "(Other)" in f1_gym:
                                continue
                            f1_possible_gyms.append(f1_gym)

                        if f1_possible_gyms and not f1_flag:
                            bout_item["FIGHTER_1_GYM"] = (
                                f1_possible_gyms[-1].split("(")[0].strip()
                            )
                    else:
                        bout_item["FIGHTER_1_GYM"] = f1_gym_list[0]
                else:
                    bout_item["FIGHTER_1_GYM"] = None

                if f2_stat:
                    f2_gym_list = f2_stat.split("\n\n")
                    f2_flag = False
                    if len(f2_gym_list) > 1:
                        f2_possible_gyms = []
                        for f2_gym in f2_gym_list:
                            if "(Primary)" in f2_gym:
                                bout_item["FIGHTER_2_GYM"] = f2_gym.replace(
                                    "(Primary)", ""
                                ).strip()
                                f2_flag = True
                                break

                            if "(Other)" in f2_gym:
                                continue
                            f2_possible_gyms.append(f2_gym)

                        if f2_possible_gyms and not f2_flag:
                            bout_item["FIGHTER_2_GYM"] = (
                                f2_possible_gyms[-1].split("(")[0].strip()
                            )
                    else:
                        bout_item["FIGHTER_2_GYM"] = f2_gym_list[0]
                else:
                    bout_item["FIGHTER_2_GYM"] = None

        yield bout_item

        fighter_urls = [response.urljoin(f1_url), response.urljoin(f2_url)]
        for fighter_url in fighter_urls:
            yield response.follow(
                fighter_url,
                callback=self.parse_fighter,
            )

    def parse_fighter(self, response):
        fighter_item = TapologyFighterItem()

        fighter_item["FIGHTER_ID"] = response.url.split("/")[-1]
        fighter_item["FIGHTER_NAME"] = (
            response.css("div.fighterUpcomingHeader > h1::text").getall()[-1].strip()
        )
        fighter_item["NATIONALITY"] = (
            response.css("div.fighterUpcomingHeader > h2#flag > a::attr(title)")
            .get()
            .replace("See all ", "")
            .replace(" Fighters", "")
            .strip()
        )

        details = [
            w3lib.html.remove_tags(x).strip()
            for x in response.css(
                "div.details.details_two_columns > ul.clearfix > li"
            ).getall()
        ]
        for detail in details:
            if detail.startswith("Age:"):
                dob = detail.split("| ")[1].replace("Date of Birth:", "").strip()
                fighter_item["DATE_OF_BIRTH"] = (
                    pd.to_datetime(dob).strftime("%Y-%m-%d") if dob != "N/A" else None
                )
            elif detail.startswith("Height:"):
                height, reach = detail.split("| ")
                height = height.replace("Height:", "").split(" (")[0].strip()
                reach = reach.replace("Reach:", "").split(" (")[0].strip()
                fighter_item["HEIGHT_INCHES"] = (
                    convert_height(height.replace("'", "' "))
                    if height != "N/A"
                    else None
                )
                fighter_item["REACH_INCHES"] = (
                    float(reach.replace('"', "")) if reach != "N/A" else None
                )

        fighter_links = response.css(
            "div.details.details_two_columns > ul.clearfix > li > div.externalIconsHolder > a::attr(href)"
        ).getall()
        ufcstats_fighter_id = sherdog_fighter_id = None
        for link in fighter_links:
            if "www.ufcstats.com/fighter-details/" in link:
                ufcstats_fighter_id = link.split("/")[-1]
            elif "www.sherdog.com/fighter/" in link:
                sherdog_fighter_id = link.split("/")[-1]
        fighter_item["UFCSTATS_FIGHTER_ID"] = ufcstats_fighter_id
        fighter_item["SHERDOG_FIGHTER_ID"] = sherdog_fighter_id

        yield fighter_item
