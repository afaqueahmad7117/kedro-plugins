from unittest.mock import patch

import pandas as pd
import pytest
from deltalake import DataCatalog
from kedro.io import DataSetError
from pandas.testing import assert_frame_equal

from kedro_datasets.pandas import DeltaTableDataSet


@pytest.fixture
def filepath(tmp_path):
    return (tmp_path / "test-delta-table").as_posix()


@pytest.fixture
def dummy_df():
    return pd.DataFrame({"col1": [1, 2], "col2": [4, 5], "col3": [5, 6]})


@pytest.fixture
def deltatable_data_set_from_path(filepath, load_args, save_args, fs_args):
    return DeltaTableDataSet(
        filepath=filepath,
        load_args=load_args,
        save_args=save_args,
        fs_args=fs_args,
    )


class TestDeltaTableDataSet:
    def test_save_to_empty_dir(self, deltatable_data_set_from_path, dummy_df):
        """Test saving to an empty directory (first time creation of delta table)."""
        deltatable_data_set_from_path.save(dummy_df)
        reloaded = deltatable_data_set_from_path.load()
        assert_frame_equal(dummy_df, reloaded)

    def test_overwrite_with_same_schema(self, deltatable_data_set_from_path, dummy_df):
        """Test saving with the default overwrite mode with new data of same schema."""
        deltatable_data_set_from_path.save(dummy_df)
        new_df = pd.DataFrame({"col1": [0, 0], "col2": [1, 1], "col3": [2, 2]})
        deltatable_data_set_from_path.save(new_df)
        reloaded = deltatable_data_set_from_path.load()
        assert_frame_equal(new_df, reloaded)

    def test_overwrite_with_diff_schema(self, deltatable_data_set_from_path, dummy_df):
        """Test saving with the default overwrite mode with new data of diff schema."""
        deltatable_data_set_from_path.save(dummy_df)
        new_df = pd.DataFrame({"new_col": [1, 2]})
        pattern = "Schema of data does not match table schema"
        with pytest.raises(DataSetError, match=pattern):
            deltatable_data_set_from_path.save(new_df)

    @pytest.mark.parametrize("save_args", [{"overwrite_schema": True}], indirect=True)
    def test_overwrite_both_data_and_schema(
        self, deltatable_data_set_from_path, dummy_df
    ):
        """Test saving to overwrite both data and schema."""
        deltatable_data_set_from_path.save(dummy_df)
        new_df = pd.DataFrame({"new_col": [1, 2]})
        deltatable_data_set_from_path.save(new_df)
        reloaded = deltatable_data_set_from_path.load()
        assert_frame_equal(new_df, reloaded)

    @pytest.mark.parametrize("save_args", [{"mode": "append"}], indirect=True)
    def test_append(self, deltatable_data_set_from_path, dummy_df):
        """Test saving by appending new data."""
        deltatable_data_set_from_path.save(dummy_df)
        new_df = pd.DataFrame({"col1": [0, 0], "col2": [1, 1], "col3": [2, 2]})
        appended = pd.concat([dummy_df, new_df], ignore_index=True)
        deltatable_data_set_from_path.save(new_df)
        reloaded = deltatable_data_set_from_path.load()
        assert_frame_equal(appended, reloaded)

    def test_versioning(self, filepath, dummy_df):
        """Test loading different versions."""
        deltatable_data_set_from_path = DeltaTableDataSet(filepath)
        deltatable_data_set_from_path.save(dummy_df)
        assert deltatable_data_set_from_path.get_loaded_version() == 0
        new_df = pd.DataFrame({"col1": [0, 0], "col2": [1, 1], "col3": [2, 2]})
        deltatable_data_set_from_path.save(new_df)
        assert deltatable_data_set_from_path.get_loaded_version() == 1

        deltatable_data_set_from_path0 = DeltaTableDataSet(
            filepath, load_args={"version": 0}
        )
        version_0 = deltatable_data_set_from_path0.load()
        assert deltatable_data_set_from_path0.get_loaded_version() == 0
        assert_frame_equal(dummy_df, version_0)

        deltatable_data_set_from_path1 = DeltaTableDataSet(
            filepath, load_args={"version": 1}
        )
        version_1 = deltatable_data_set_from_path1.load()
        assert deltatable_data_set_from_path1.get_loaded_version() == 1
        assert_frame_equal(new_df, version_1)

    def test_filepath_and_catalog_both_exist(self, filepath):
        """Test when both filepath and catalog are provided."""
        with pytest.raises(DataSetError):
            DeltaTableDataSet(filepath=filepath, catalog_type="AWS")

    def test_property_schema(self, deltatable_data_set_from_path, dummy_df):
        """Test the schema property to return the underlying delta table schema."""
        deltatable_data_set_from_path.save(dummy_df)
        s1 = deltatable_data_set_from_path.schema
        s2 = deltatable_data_set_from_path._delta_table.schema().json()
        assert s1 == s2

    def test_describe(self, filepath):
        """Test the describe method."""
        deltatable_data_set_from_path = DeltaTableDataSet(filepath)
        desc = deltatable_data_set_from_path._describe()
        assert desc["filepath"] == filepath
        assert desc["version"] is None

    @patch("kedro_datasets.pandas.deltatable_dataset.DeltaTable")
    def test_from_aws_glue_catalog(self, mock_delta_table):
        """Test dataset creation from AWS Glue catalog."""
        _ = DeltaTableDataSet(catalog_type="AWS", database="db", table="tbl")
        mock_delta_table.from_data_catalog.assert_called_once()
        mock_delta_table.from_data_catalog.assert_called_with(
            data_catalog=DataCatalog.AWS,
            data_catalog_id=None,
            database_name="db",
            table_name="tbl",
        )

    @patch("kedro_datasets.pandas.deltatable_dataset.DeltaTable")
    def test_from_databricks_unity_catalog(self, mock_delta_table):
        """Test dataset creation from Databricks Unity catalog."""
        _ = DeltaTableDataSet(
            catalog_type="UNITY", catalog_name="id", database="db", table="tbl"
        )
        mock_delta_table.from_data_catalog.assert_called_once()
        mock_delta_table.from_data_catalog.assert_called_with(
            data_catalog=DataCatalog.UNITY,
            data_catalog_id="id",
            database_name="db",
            table_name="tbl",
        )

    def test_from_unsupported_catalog(self):
        """Test dataset creation from unsupported catalog."""
        with pytest.raises(KeyError):
            DeltaTableDataSet(catalog_type="unsupported", database="db", table="tbl")