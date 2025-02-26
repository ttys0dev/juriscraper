# Author: Michael Lissner
# Date created: 2013-06-03
# Date updated: 2020-02-25

import re

from juriscraper.lib.exceptions import InvalidDocumentError
from juriscraper.OpinionSiteLinear import OpinionSiteLinear


class Site(OpinionSiteLinear):
    base_url = "https://juddocumentservice.mt.gov"
    download_base = f"{base_url}/getDocByCTrackId?DocId="
    cite_regex = r"((19|20)\d{2}\sMT\s\d{1,3}[A-Z]?)"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.court_id = self.__module__
        self.url = f"{self.base_url}/getDailyOrders"
        self.expected_content_types = None

    def _process_html(self):
        for row in self.html:
            description = row["documentDescription"]
            if not description.startswith("Opinion"):
                # skip orders and just do opinions
                continue

            status = (
                "Published" if "Published" in description else "Unpublished"
            )

            docket = row["caseNumber"]
            if docket.startswith("DA"):
                nature = "Direct Appeal"
            elif docket.startswith("OP"):
                nature = "Original Proceeding"
            elif docket.startswith("PR"):
                nature = "Professional Regulation"
            elif docket.startswith("AF"):
                nature = "Administrative File"
            else:
                nature = "Unknown"

            author = ""
            disposition = ""
            summary = ""
            if author_match := re.search(
                r"Justice (?P<author>.*?)\s*(?:author(ed)?|,|-|\.)",
                description,
                re.I,
            ):
                author = author_match.group("author")
                disposition = description[author_match.end() :].strip(" .,-")
                disposition = disposition[:1].upper() + disposition[1:]
            else:
                summary = description

            self.cases.append(
                {
                    "url": self.download_base + row["cTrackId"],
                    "status": status,
                    "date": row["fileDate"],
                    "name": row["title"],
                    "docket": docket,
                    "nature_of_suit": nature,
                    "author": author,
                    "disposition": disposition,
                    "summary": summary,
                }
            )

    def extract_from_text(self, scraped_text: str) -> dict:
        """Extract citation from text

        :param scraped_text: Text of scraped content
        :return: date filed
        """
        first_text = scraped_text[:400]
        if match := re.search(self.cite_regex, first_text):
            return {"Citation": match.group(0)}
        return {}

    @staticmethod
    def cleanup_content(content: str) -> str:
        """Raise an error if the content is invalid; otherwise just return it

        Not cleaning up in the common sense; but avoids ingesting error
        pages. This source does not mark the error page with an error status
        and does not have content type headers; so we can't detect the error
        through standard controls

        :param content: the downloaded content
        :return: the downloaded content, unchanged
        """
        if "No document found with CTrack ID" in content[:1000]:
            raise InvalidDocumentError(content)
        return content
