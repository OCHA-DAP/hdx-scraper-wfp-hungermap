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
            project_config_yaml=join("config", "project_configuration.yaml"),
        )
        UserAgent.set_global("test")
        Country.countriesdata(use_live=False)
        Locations.set_validlocations(
            [
                {"name": "cod", "title": "cod"},
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
                "test_wfp_hungermaps", delete_on_success=True,
                delete_on_failure=False
        ) as folder:
            with Download() as downloader:
                retriever = Retrieve(
                    downloader, folder, input_folder, folder, False, True
                )
                today = parse_date("2023-12-05")
                hungermaps = HungerMaps(configuration, retriever, folder,
                                        today)
                state_dict = {"DEFAULT": parse_date("2022-01-01")}
                countries = hungermaps.get_country_data(state_dict,
                                                        max_days_ago=5)
                assert len(countries) == 35

                rows, earliest_date, latest_date = hungermaps.get_rows(
                    "COD", max_months_ago=5
                )
                assert len(rows) == 3620
                assert earliest_date == parse_date("2023-07-05")
                assert latest_date == parse_date("2023-11-20")

                (
                    dataset,
                    showcase,
                    bites_disabled,
                ) = hungermaps.generate_dataset_and_showcase(
                    "COD", rows, earliest_date, latest_date
                )
                assert dataset == {
                    "data_update_frequency": "-2",
                    "dataset_date": "[2023-07-05T00:00:00 TO 2023-11-20T23:59:59]",
                    "groups": [{"name": "cod"}],
                    "maintainer": "196196be-6037-4488-8b71-d786adf4c081",
                    "name": "wfp-hungermap-data-for-cod",
                    "owner_org": "3ecac442-7fed-448d-8f78-b385ef6f84e7",
                    "subnational": "1",
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
                    "title": "Democratic Republic of the Congo - HungerMap data",
                }
                resources = dataset.get_resources()
                assert resources == [
                    {
                        "description": "Democratic Republic of the Congo - HungerMap data",
                        "format": "csv",
                        "name": "wfp-hungermap-data-for-cod.csv",
                        "resource_type": "file.upload",
                        "url_type": "upload",
                    },
                    {
                        "description": "Democratic Republic of the Congo - HungerMap data long "
                                       "format",
                        "format": "csv",
                        "name": "wfp-hungermap-data-for-cod-long.csv",
                        "resource_type": "file.upload",
                        "url_type": "upload",
                    },
                ]
                for resource in resources:
                    filename = resource["name"]
                    expected_path = join(fixtures, filename)
                    actual_path = join(folder, filename)
                    assert_files_same(expected_path, actual_path)

                assert showcase == {
                    "image_url": "https://www.wfp.org/sites/default/files/2020-11/migrated-story-hero-images/1%2AwHonqWsryfHjnj3FRQS_xA.png",
                    "name": "wfp-hungermap-data-for-cod-showcase",
                    "notes": "HungerMap LIVE",
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
                    "title": "Democratic Republic of the Congo - HungerMap data showcase",
                    "url": "https://hungermap.wfp.org/",
                }

                assert bites_disabled == (False, False, True)

                assert state_dict == {
                    "AGO": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "BEN": datetime(2022, 1, 11, 0, 0, tzinfo=timezone.utc),
                    "BFA": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "CAF": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "CIV": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "CMR": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "COD": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "COG": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "COL": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "DEFAULT": datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc),
                    "ETH": datetime(2023, 6, 12, 0, 0, tzinfo=timezone.utc),
                    "GIN": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "GTM": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "HND": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "HTI": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "IRQ": datetime(2023, 5, 7, 0, 0, tzinfo=timezone.utc),
                    "KEN": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "LAO": datetime(2023, 7, 26, 0, 0, tzinfo=timezone.utc),
                    "MDG": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "MLI": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "MOZ": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "MRT": datetime(2023, 7, 13, 0, 0, tzinfo=timezone.utc),
                    "MWI": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "NAM": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "NER": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "NGA": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "SLE": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "SLV": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "SOM": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "SYR": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "TCD": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "TZA": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "UKR": datetime(2023, 9, 3, 0, 0, tzinfo=timezone.utc),
                    "YEM": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "ZMB": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                    "ZWE": datetime(2023, 10, 13, 0, 0, tzinfo=timezone.utc),
                }
