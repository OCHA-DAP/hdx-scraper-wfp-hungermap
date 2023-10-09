#!/usr/bin/python
"""
Unit tests for WFP ADAM.

"""
from datetime import datetime, timezone
from os.path import join

import pytest
from hdx.api.configuration import Configuration
from hdx.api.locations import Locations
from hdx.data.vocabulary import Vocabulary
from hdx.location.country import Country
from hdx.utilities.compare import assert_files_same
from hdx.utilities.dateparse import parse_date
from hdx.utilities.downloader import Download
from hdx.utilities.path import temp_dir
from hdx.utilities.retriever import Retrieve
from hdx.utilities.useragent import UserAgent
from wfp import HungerMaps


class TestHungerMaps:
    @pytest.fixture(scope="function")
    def fixtures(self):
        return join("tests", "fixtures")

    @pytest.fixture(scope="function")
    def input_folder(self, fixtures):
        return join(fixtures, "input")

    @pytest.fixture(scope="function")
    def configuration(self):
        Configuration._create(
            hdx_read_only=True,
            user_agent="test",
            project_config_yaml=join("config", "project_configuration.yml"),
        )
        UserAgent.set_global("test")
        Country.countriesdata(use_live=False)
        Locations.set_validlocations(
            [
                {"name": "afg", "title": "afg"},
            ]
        )
        configuration = Configuration.read()
        tags = (
            "hxl",
            "indicators",
            "food security",
        )
        Vocabulary._tags_dict = {tag: {"Action to Take": "ok"} for tag in tags}
        tags = [{"name": tag} for tag in tags]
        Vocabulary._approved_vocabulary = {
            "tags": tags,
            "id": "4e61d464-4943-4e97-973a-84673c1aaa87",
            "name": "approved",
        }
        return configuration

    def test_generate_datasets_and_showcases(
        self,
        configuration,
        input_folder,
        fixtures,
    ):
        with temp_dir(
            "test_wfp_hungermaps", delete_on_success=True, delete_on_failure=False
        ) as folder:
            with Download() as downloader:
                retriever = Retrieve(
                    downloader, folder, input_folder, folder, False, True
                )
                today = parse_date("2023-10-09")
                hungermaps = HungerMaps(configuration, retriever, folder, today)
                update, countries = hungermaps.get_country_data(
                    {"DEFAULT": parse_date("2022-01-01")}
                )
                assert update is True
                assert len(countries) == 88

                rows, earliest_date, latest_date = hungermaps.get_rows("AFG")
                assert len(rows) == 12412
                assert earliest_date == parse_date("2022-10-09")
                assert latest_date == parse_date("2023-10-08")

                dataset = hungermaps.generate_dataset(
                    "AFG", rows, earliest_date, latest_date
                )
                assert dataset == {
                    "name": "wfp-hungermap-data-for-afg",
                    "title": "Afghanistan - HungerMap data",
                    "maintainer": "196196be-6037-4488-8b71-d786adf4c081",
                    "owner_org": "3ecac442-7fed-448d-8f78-b385ef6f84e7",
                    "data_update_frequency": "-1",
                    "subnational": "1",
                    "groups": [{"name": "afg"}],
                    "tags": [
                        {
                            "name": "hxl",
                            "vocabulary_id": "4e61d464-4943-4e97-973a-84673c1aaa87",
                        },
                        {
                            "name": "indicators",
                            "vocabulary_id": "4e61d464-4943-4e97-973a-84673c1aaa87",
                        },
                        {
                            "name": "food security",
                            "vocabulary_id": "4e61d464-4943-4e97-973a-84673c1aaa87",
                        },
                    ],
                    "dataset_date": "[2022-10-09T00:00:00 TO 2023-10-08T23:59:59]",
                }
                resources = dataset.get_resources()
                assert resources == [
                    {
                        "name": "wfp-hungermap-data-for-afg.csv",
                        "description": "Afghanistan - HungerMap data",
                        "format": "csv",
                        "resource_type": "file.upload",
                        "url_type": "upload",
                    }
                ]
                resource = resources[0]

                filename = resource["name"]
                expected_path = join(fixtures, filename)
                actual_path = join(folder, filename)
                assert_files_same(expected_path, actual_path)