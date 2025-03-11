#!/usr/bin/python
"""
Top level script. Calls other functions that generate datasets that this script then creates in HDX.

"""
import logging
from copy import deepcopy
from os.path import expanduser, join

from hdx.api.configuration import Configuration
from hdx.data.dataset import Dataset
from hdx.facades.infer_arguments import facade
from hdx.utilities.dateparse import now_utc
from hdx.utilities.downloader import Download
from hdx.utilities.path import progress_storing_folder, wheretostart_tempdir_batch
from hdx.utilities.retriever import Retrieve
from hdx.utilities.state import State
from slugify import slugify
from wfp import HungerMaps

logger = logging.getLogger(__name__)

lookup = "hdx-scraper-wfp-hungermap"
updated_by_script = "HDX Scraper: WFP HungerMap"


def main(save: bool = False, use_saved: bool = False) -> None:
    """Generate datasets and create them in HDX

    Args:
        save (bool): Save downloaded data. Defaults to False.
        use_saved (bool): Use saved data. Defaults to False.

    Returns:
        None
    """

    configuration = Configuration.read()
    with State(
        "metric_dates.txt",
        State.dates_str_to_country_date_dict,
        State.country_date_dict_to_dates_str,
    ) as state:
        state_dict = deepcopy(state.get())
        with wheretostart_tempdir_batch(lookup) as info:
            folder = info["folder"]
            with Download(rate_limit={"calls": 1, "period": 0.1}) as downloader:
                retriever = Retrieve(
                    downloader, folder, "saved_data", folder, save, use_saved
                )
                today = now_utc()
                hungermaps = HungerMaps(configuration, retriever, folder, today)
                countries = hungermaps.get_country_data(state_dict, max_days_ago=10)
                logger.info(f"Number of datasets: {len(countries)}")
                for _, countryinfo in progress_storing_folder(info, countries, "iso3"):
                    countryiso3 = countryinfo["iso3"]
                    rows, earliest_date, latest_date, has_subnational = hungermaps.get_rows(countryiso3)
                    (
                        dataset,
                        showcase,
                        bites_disabled,
                    ) = hungermaps.generate_dataset_and_showcase(
                        countryiso3, rows, earliest_date, latest_date, has_subnational
                    )
                    if not dataset:
                        continue
                    dataset.update_from_yaml(join("config", "hdx_dataset_static.yaml"))
                    # ensure markdown has line breaks
                    dataset["notes"] = dataset["notes"].replace("\n", "  \n")

                    dataset.generate_quickcharts(bites_disabled=bites_disabled)
                    dataset.create_in_hdx(
                        remove_additional_resources=True,
                        hxl_update=False,
                        updated_by_script=updated_by_script,
                        batch=info["batch"],
                    )
                    if showcase:
                        showcase.create_in_hdx()
                        showcase.add_dataset(dataset)

                dataset_name_prefix = slugify(hungermaps.dataset_name_prefix)
                for dataset in Dataset.search_in_hdx(fq="organization:wfp"):
                    name = dataset["name"]
                    if name.startswith(dataset_name_prefix):
                        if (
                            dataset.get_location_iso3s()[0]
                            not in hungermaps.get_shared_countries()
                        ):
                            logger.info(f"Deleting {name}!")
                            dataset.delete_from_hdx()
        state.set(state_dict)


if __name__ == "__main__":
    facade(
        main,
        user_agent_config_yaml=join(expanduser("~"), ".useragents.yaml"),
        user_agent_lookup=lookup,
        project_config_yaml=join("config", "project_configuration.yaml"),
    )
