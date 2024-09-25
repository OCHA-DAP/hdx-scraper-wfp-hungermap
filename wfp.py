#!/usr/bin/python
"""
WFP Hunger Maps:
---------------

Reads WFP Hunger Maps data and creates datasets.

"""
import logging
from copy import copy

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

long_hxltags = {
    "countrycode": "#country+code",
    "countryname": "#country+name",
    "adminone": "#adm1+name",
    "adminlevel": "#meta+adminlevel",
    "date": "#date",
    "datatype": "#data+type",
    "indicator name": "#indicator+name",
    "population": "#population",
    "prevalence": "#indicator+prevalence",
}


class HungerMaps:
    dataset_name_prefix = "wfp hungermap data for "

    def __init__(self, configuration, retriever, folder, today):
        self.configuration = configuration
        self.retriever = retriever
        self.folder = folder
        self.today = today
        self.shared_countries = set()
        self.countries_data = {}

    def get_country_data(self, state, max_days_ago=365):
        try:
            country_url = self.configuration["country_url"]
            for days_ago in range(0, max_days_ago, 1):
                url = f"{country_url}?days_ago={days_ago}"
                json = self.retriever.download_json(url)
                if json.get("statusCode") != "200":
                    logger.info(f"No national data available!")
                    continue
                for country in json["body"]["countries"]:
                    datatype = country["dataType"]
                    if datatype == "PREDICTION":
                        continue
                    countryiso3 = country["country"]["iso3"]
                    self.shared_countries.add(countryiso3)
                    date = parse_date(country["date"])
                    if date > state.get(countryiso3, state["DEFAULT"]):
                        state[countryiso3] = date
                        self.countries_data[countryiso3] = [country]
                    else:
                        current_rows = self.countries_data.get(countryiso3)
                        if not current_rows:
                            continue
                        current_date = current_rows[-1]["date"]
                        date = country["date"]
                        if date != current_date:
                            self.countries_data[countryiso3].append(country)
        except DownloadError:
            logger.info(f"No national data available!")

        return [{"iso3": countryiso3} for countryiso3 in self.countries_data]

    def get_rows(self, countryiso3, max_months_ago=12):
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

        country_rows = self.countries_data[countryiso3]
        rows.extend([get_row(country_row) for country_row in country_rows])
        country_url = self.configuration["country_url"]
        end_date = self.today - relativedelta(days=1)
        start_date = self.today - relativedelta(months=1)

        def add_subnational_rows(sd, ed):
            url = f"{country_url}/{countryiso3}/region?date_start={sd.date().isoformat()}&date_end={ed.date().isoformat()}"
            try:
                json = self.retriever.download_json(url)
                if json.get("statusCode") != "200":
                    logger.info(f"No subnational data for {countryname}!")
                    return
                all_adminone_data = json["body"]
                for adminone_data in all_adminone_data:
                    datatype = adminone_data["dataType"]
                    if datatype == "PREDICTION":
                        continue
                    adminone = adminone_data["region"]["name"]
                    population = adminone_data["region"]["population"]
                    rows.append(get_row(adminone_data, adminone, population))
            except DownloadError:
                logger.info(f"No subnational data for {countryname}!")

        for month in range(0, max_months_ago):
            add_subnational_rows(start_date, end_date)
            start_date = start_date - relativedelta(months=1)
            end_date = end_date - relativedelta(months=1)

        class reverser:
            def __init__(self, obj):
                self.obj = obj

            def __eq__(self, other):
                return other.obj == self.obj

            def __lt__(self, other):
                return other.obj < self.obj

        rows = sorted(
            rows,
            key=lambda x: (
                x["adminlevel"],
                reverser(x["date"]),
                x["adminone"] if x["adminone"] else "ZZZ",
            ),
        )
        return rows, earliest_date, latest_date

    @classmethod
    def get_name(cls, countryiso3):
        return f"{cls.dataset_name_prefix}{countryiso3}"

    def generate_dataset_and_showcase(
        self, countryiso3, rows, earliest_date, latest_date
    ):
        name = self.get_name(countryiso3)
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
        dataset.set_expected_update_frequency("As needed")
        dataset.set_subnational(True)
        dataset.add_country_location(countryiso3)
        tags = ["hxl", "indicators", "food security"]
        dataset.add_tags(tags)
        dataset.set_time_period(earliest_date, latest_date)

        filename = f"{slugified_name}.csv"
        resourcedata = {"name": filename, "description": title}
        dataset.generate_resource_from_rows(self.folder, filename, rows, resourcedata)
        long_rows = [long_hxltags]
        latest_date = default_date
        latest_row = None
        for row in rows[1:]:
            date = parse_date(row["date"])
            if date > latest_date:
                latest_date = date
                latest_row = row
            base_row = {}
            for col in row.keys():
                if col in (
                    "countrycode",
                    "countryname",
                    "adminone",
                    "adminlevel",
                    "date",
                    "datatype",
                ):
                    base_row[col] = row[col]
            population = row["population"]
            if population:
                new_row = copy(base_row)
                new_row["indicator name"] = "total"
                new_row["population"] = population
                new_row["prevalence"] = ""
                long_rows.append(new_row)

            def add_indicator(indicator_name):
                population = row[f"{indicator_name} people"]
                if population:
                    new_row = copy(base_row)
                    new_row["indicator name"] = indicator_name
                    new_row["population"] = population
                    new_row["prevalence"] = row[f"{indicator_name} prevalence"]
                    long_rows.append(new_row)

            add_indicator("fcs")
            add_indicator("rcsi")
            add_indicator("health access")
            add_indicator("market access")

        filename = f"{slugified_name}-long.csv"
        resourcedata = {"name": filename, "description": f"{title} long format"}
        dataset.generate_resource_from_rows(
            self.folder, filename, long_rows, resourcedata
        )
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

        fcs = latest_row.get("fcs prevalence")
        if fcs:
            fcs = False
        else:
            fcs = True
        rcsi = latest_row.get("rcsi prevalence")
        if rcsi:
            rcsi = False
        else:
            rcsi = True
        health = latest_row.get("health prevalence")
        if health:
            health = False
        else:
            health = True
        return dataset, showcase, (fcs, rcsi, health)

    def get_shared_countries(self):
        return self.shared_countries
