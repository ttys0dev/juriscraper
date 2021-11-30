import feedparser
from lxml.html import fromstring

from juriscraper.lib.string_utils import titlecase
from juriscraper.OpinionSiteLinear import OpinionSiteLinear


class Site(OpinionSiteLinear):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = "https://cafc.uscourts.gov/category/opinion-order/feed/"
        self.court_id = self.__module__

    def _process_html(self) -> None:
        """Process the RSS feed.

        Iterate over each item in the RSS feed to extract out
        the date, case name, docket number, and status and pdf URL.
        Return: None
        """
        feed = feedparser.parse(self.request["response"].content)
        for item in feed["entries"]:
            value = item["content"][0]["value"]
            docket, title = item["title"].split(" [")[0].split(": ")

            self.cases.append(
                {
                    "date": item["published"],
                    "docket": docket,
                    "url": fromstring(value).xpath(".//a/@href")[0],
                    "name": titlecase(title),
                    "status": self._get_status(item["title"].lower()),
                }
            )

    def _get_status(self, title: str) -> str:
        """Get precedential status from title string.

        return: The precedential status of the case.
        """
        if "nonprecedential" in title:
            status = "Unpublished"
        elif "precedential" in title:
            status = "Published"
        else:
            status = "Unknown"
        return status
