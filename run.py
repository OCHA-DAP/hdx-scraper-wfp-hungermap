#!/usr/bin/python
"""
Top level script. Calls other functions that generate datasets that this script then creates in HDX.

"""
import logging
from copy import deepcopy
from os.path import expanduser, join

from hdx.api.configuration import Configuration
from hdx.facades.infer_arguments import facade
from hdx.utilities.dateparse import iso_string_from_datetime, now_utc, parse_date
from hdx.utilities.downloader import Download
from hdx.utilities.path import progress_storing_folder, wheretostart_tempdir_batch
from hdx.utilities.retriever import Retrieve
from hdx.utilities.state import State
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
            with Download() as downloader:
                retriever = Retrieve(
                    downloader, folder, "saved_data", folder, save, use_saved
                )
                today = now_utc()
                hungermaps = HungerMaps(configuration, retriever, folder, today)
                update, countries = hungermaps.get_country_data(state_dict)
                logger.info(f"Number of datasets: {len(countries)}")
                if update:
                    for _, countryinfo in progress_storing_folder(
                        info, countries, "iso3"
                    ):
                        countryiso3 = countryinfo["iso3"]
                        rows, earliest_date, latest_date = hungermaps.get_rows(
                            countryiso3
                        )
                        dataset, showcase = hungermaps.generate_dataset_and_showcase(
                            countryiso3, rows, earliest_date, latest_date
                        )
                        if not dataset:
                            continue
                        dataset.update_from_yaml(
                            join("config", "hdx_dataset_static.yml")
                        )
                        # ensure markdown has line breaks
                        dataset["notes"] = dataset["notes"].replace("\n", "  \n")

                        dataset.create_in_hdx(
                            remove_additional_resources=True,
                            hxl_update=False,
                            updated_by_script=updated_by_script,
                            batch=info["batch"],
                        )
                        if showcase:
                            showcase.create_in_hdx()
                            showcase.add_dataset(dataset)
        state.set(state_dict)


if __name__ == "__main__":
    facade(
        main,
        user_agent_config_yaml=join(expanduser("~"), ".useragents.yml"),
        user_agent_lookup=lookup,
        project_config_yaml=join("config", "project_configuration.yml"),
    )
