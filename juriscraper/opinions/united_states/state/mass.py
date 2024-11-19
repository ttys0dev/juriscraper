"""
Scraper for Massachusetts Supreme Court
CourtID: mass
Court Short Name: MS
Author: Andrei Chelaru
Court Contact: SJCReporter@sjc.state.ma.us (617) 557-1030
Reviewer: mlr
History:
 - 2014-07-12: Created.
 - 2014-08-05, mlr: Updated regex.
 - 2014-09-18, mlr: Updated regex.
 - 2016-09-19, arderyp: Updated regex.
 - 2017-11-29, arderyp: Moved from RSS source to HTML
    parsing due to website redesign
 - 2023-01-28, William Palin: Updated scraper
"""

from lxml import etree, html

from juriscraper.lib.html_utils import strip_bad_html_tags_insecure
from juriscraper.OpinionSiteLinear import OpinionSiteLinear


class Site(OpinionSiteLinear):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = "https://www.socialaw.com/customapi/slips/getopinions"
        self.court_id = self.__module__
        self.court_name = "Supreme Judicial Court"
        self.status = "Published"

    def _process_html(self):
        """Scrape and process the JSON endpoint

        :return: None
        """
        for row in self.html:
            if row["SectionName"] != self.court_name:
                continue
            self.cases.append(
                {
                    "name": row.get("Parties"),
                    "judge": (
                        row["Details"]["Present"]
                        if "JJ" in row["Details"]["Present"]
                        else ""
                    ),
                    "date": row["Date"],
                    # "headnotes": row['Details']['Keywords'],
                    "summary": row["Details"]["ShortOpinion"],
                    "url": f"https://www.socialaw.com/services/slip-opinions/{row['UrlName']}",
                    "docket": row["Details"]["Docket"],
                }
            )

    @staticmethod
    def cleanup_content(content):
        """Remove non-opinion HTML

        Cleanup HMTL from Social Law page so we can properly display the content

        :param content: The scraped HTML
        :return: Cleaner HTML
        """
        content = content.decode("utf-8")
        tree = strip_bad_html_tags_insecure(content, remove_scripts=True)
        content = tree.xpath(
            "//div[@id='contentPlaceholder_ctl00_ctl00_ctl00_detailContainer']"
        )[0]
        new_tree = etree.Element("html")
        body = etree.SubElement(new_tree, "body")
        body.append(content)
        return html.tostring(new_tree, pretty_print=True, encoding="unicode")
