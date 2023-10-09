#!/usr/bin/python
"""
WFP Hunger Maps:
---------------

Reads WFP Hunger Maps data and creates datasets.

"""
import logging

from dateutil.relativedelta import relativedelta
from hdx.data.dataset import Dataset
from hdx.data.showcase import Showcase
from hdx.location.country import Country
from hdx.utilities.base_downloader import DownloadError
from hdx.utilities.dateparse import default_date, default_enddate, parse_date
from slugify import slugify

logger = logging.getLogger(__name__)


hxltags = {
    "countrycode": "#country+code",
    "countryname": "#country+name",
    "adminone": "#adm1+name",
    "adminlevel": "#meta+adminlevel",
    "population": "#population+total",
    "date": "#date",
    "datatype": "#data+type",
    "fcs people": "#population+fcs",
    "fcs prevalence": "#indicator+fcs+prevalence",
    "rcsi people": "#population+rcsi",
    "rcsi prevalence": "#indicator+rcsi+prevalence",
    "health access people": "#population+health_access",
    "health access prevalence": "#indicator+health_access+prevalence",
    "market access people": "#population+market_access",
    "market access prevalence": "#indicator+market_access+prevalence",
}


class HungerMaps:
    def __init__(self, configuration, retriever, folder, today):
        self.configuration = configuration
        self.retriever = retriever
        self.folder = folder
        self.today = today
        self.countries_data = {}

    def get_country_data(self, state):
        url = self.configuration["country_url"]
        json = self.retriever.download_json(url)

        update = False
        for country in json["countries"]:
            countryiso3 = country["country"]["iso3"]
            date = parse_date(country["date"])
            if date > state.get(countryiso3, state["DEFAULT"]):
                state[countryiso3] = date
                self.countries_data[countryiso3] = country
                update = True
        countries = [{"iso3": countryiso3} for countryiso3 in self.countries_data]
        return update, countries

    def get_rows(self, countryiso3):
        rows = [hxltags]
        countryname = Country.get_country_name_from_iso3(countryiso3)

        earliest_date = default_enddate
        latest_date = default_date

        def get_row(data, adminone="", population=""):
            nonlocal earliest_date, latest_date

            if adminone:
                adminlevel = "subnational"
            else:
                adminlevel = "national"

            def get_metric(metric):
                metric_data = data["metrics"].get(metric)
                if not metric_data:
                    metric_data = {"people": "", "prevalence": ""}
                return metric_data

            fcs = get_metric("fcs")
            rcsi = get_metric("rcsi")
            health_access = get_metric("healthAccess")
            market_access = get_metric("marketAccess")

            date = parse_date(data["date"])
            if date < earliest_date:
                earliest_date = date
            if date > latest_date:
                latest_date = date
            return {
                "countrycode": countryiso3,
                "countryname": countryname,
                "adminone": adminone,
                "adminlevel": adminlevel,
                "population": population,
                "date": date.date().isoformat(),
                "datatype": data["dataType"],
                "fcs people": fcs["people"],
                "fcs prevalence": fcs["prevalence"],
                "rcsi people": rcsi["people"],
                "rcsi prevalence": rcsi["prevalence"],
                "health access people": health_access["people"],
                "health access prevalence": health_access["prevalence"],
                "market access people": market_access["people"],
                "market access prevalence": market_access["prevalence"],
            }

        country_data = self.countries_data[countryiso3]
        rows.append(get_row(country_data))
        url = self.configuration["country_url"]
        today = self.today.date().isoformat()
        one_year_ago = (self.today - relativedelta(years=1)).date().isoformat()
        url = f"{url}/{countryiso3}/region?date_start={one_year_ago}&date_end={today}"
        try:
            all_adminone_data = self.retriever.download_json(url)
            for adminone_data in all_adminone_data:
                adminone = adminone_data["region"]["name"]
                population = adminone_data["region"]["population"]
                rows.append(get_row(adminone_data, adminone, population))
        except DownloadError:
            logger.info(f"No subnational data for {countryname}!")
        return rows, earliest_date, latest_date

    def generate_dataset_and_showcase(self, countryiso3, rows, earliest_date, latest_date):
        name = f"wfp hungermap data for {countryiso3}"
        countryname = Country.get_country_name_from_iso3(countryiso3)
        title = f"{countryname} - HungerMap data"
        logger.info(f"Creating dataset: {title}")
        slugified_name = slugify(name)
        dataset = Dataset(
            {
                "name": slugified_name,
                "title": title,
            }
        )
        dataset.set_maintainer("196196be-6037-4488-8b71-d786adf4c081")
        dataset.set_organization("3ecac442-7fed-448d-8f78-b385ef6f84e7")
        dataset.set_expected_update_frequency("Never")
        dataset.set_subnational(True)
        dataset.add_country_location(countryiso3)
        tags = ["hxl", "indicators", "food security"]
        dataset.add_tags(tags)
        dataset.set_reference_period(earliest_date, latest_date)

        filename = f"{slugified_name}.csv"
        resourcedata = {"name": filename, "description": title}
        dataset.generate_resource_from_rows(self.folder, filename, rows, resourcedata)

        showcase = Showcase(
            {
                "name": f"{slugified_name}-showcase",
                "title": f"{title} showcase",
                "notes": f"HungerMap LIVE",
                "url": "https://hungermap.wfp.org/",
                "image_url": "https://www.wfp.org/sites/default/files/2020-11/migrated-story-hero-images/1%2AwHonqWsryfHjnj3FRQS_xA.png",
            }
        )
        showcase.add_tags(tags)

        return dataset, showcase
