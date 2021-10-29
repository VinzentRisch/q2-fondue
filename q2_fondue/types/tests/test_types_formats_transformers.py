# ----------------------------------------------------------------------------
# Copyright (c) 2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import unittest

import pandas as pd
import qiime2
from qiime2.plugin import ValidationError
from qiime2.plugin.testing import TestPluginBase

from q2_fondue.types import SRAMetadata, SRAMetadataDirFmt, SRAMetadataFormat


class TestFormats(TestPluginBase):
    package = 'q2_fondue.types.tests'

    def test_sra_metadata_fmt(self):
        meta_path = self.get_data_path('sra-metadata.tsv')
        format = SRAMetadataFormat(meta_path, mode='r')
        format.validate()

    def test_sra_metadata_fmt_missing_columns(self):
        meta_path = self.get_data_path('sra-metadata-missing-columns.tsv')
        format = SRAMetadataFormat(meta_path, mode='r')
        with self.assertRaisesRegexp(
                ValidationError,
                'Some required columns are missing from the metadata file: '
                'Organism, Instrument, Platform, Bases, Bytes, Public, '
                'Library Selection, Library Source, Library Layout, Study ID.'
        ):
            format.validate()

    def test_sra_metadata_fmt_missing_ids(self):
        meta_path = self.get_data_path('sra-metadata-missing-ids.tsv')
        format = SRAMetadataFormat(meta_path, mode='r')
        with self.assertRaisesRegexp(
                ValidationError,
                'Some samples are missing IDs in the following fields: '
                'Biosample ID, Study ID'
        ):
            format.validate()


class TestTypes(TestPluginBase):
    package = 'q2_fondue.types.tests'

    def test_sra_metadata_semantic_type_registration(self):
        self.assertRegisteredSemanticType(SRAMetadata)

    def test_sra_metadata_to_format_registration(self):
        self.assertSemanticTypeRegisteredToFormat(
            SRAMetadata, SRAMetadataDirFmt)


class TestTransformers(TestPluginBase):
    package = 'q2_fondue.types.tests'

    def setUp(self):
        super().setUp()
        meta_path = self.get_data_path('sra-metadata.tsv')
        self.sra_meta = SRAMetadataFormat(meta_path, mode='r')
        self.sra_meta_df = pd.read_csv(
            meta_path, sep='\t', header=0, index_col=0, dtype='str')

    def test_dataframe_to_sra_metadata(self):
        transformer = self.get_transformer(pd.DataFrame, SRAMetadataFormat)
        obs = transformer(self.sra_meta_df)
        self.assertIsInstance(obs, SRAMetadataFormat)

        obs = pd.read_csv(
            str(obs), sep='\t', header=0, index_col=0, dtype='str')
        pd.testing.assert_frame_equal(obs, self.sra_meta_df)

    def test_sra_metadata_to_dataframe(self):
        _, obs = self.transform_format(
            SRAMetadataFormat, pd.DataFrame, 'sra-metadata.tsv'
        )
        self.assertIsInstance(obs, pd.DataFrame)
        pd.testing.assert_frame_equal(obs, self.sra_meta_df)

    def test_sra_metadata_to_q2_metadata(self):
        _, obs = self.transform_format(
            SRAMetadataFormat, qiime2.Metadata, 'sra-metadata.tsv'
        )
        exp = qiime2.Metadata(self.sra_meta_df)
        self.assertEqual(obs, exp)


if __name__ == "__main__":
    unittest.main()
