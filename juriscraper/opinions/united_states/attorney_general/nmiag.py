"""
Scraper for Commonwealth of Northern Mariana Islands Attorney General
CourtID: nmiag
Court Short Name: Northern Mariana Islands AG
Author: William E. Palin
History:
 - 2023-01-29: Created.
"""

from juriscraper.DeferringList import DeferringList
from juriscraper.OpinionSiteLinear import OpinionSiteLinear


class Site(OpinionSiteLinear):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.court_id = self.__module__
        self.status = "Published"
        self.url = "https://www.cnmioag.org/publications/"

    def _process_html(self):
        """Process html

        :return: None
        """
        self.section = self.html.xpath(
            ".//div/div/h2[text() = 'Legal Opinions']/../.."
        )[0].getnext()
        for row in self.section.xpath(".//a"):
            url = row.xpath(".//@href")[0]
            docket, name = row.text_content().strip().split(":")
            date = f"20{docket.split()[1][:2]}"
            self.cases.append(
                {
                    "url": url,
                    "docket": docket,
                    "name": name.strip(),
                    "date": date,
                    "date_filed_is_approximate": True,
                }
            )

    def _get_download_urls(self) -> DeferringList:
        """Get urls using a deferring list."""

        def get_download_url(link: str) -> str:
            """Abstract out the download link"""
            if self.test_mode_enabled():
                return link
            html = self._get_html_tree_by_url(link)
            return html.xpath(
                ".//p[contains(@class, 'embed_download')]/a/@href"
            )[0]

        links = [case["url"] for case in self.cases]
        return DeferringList(seed=links, fetcher=get_download_url)
