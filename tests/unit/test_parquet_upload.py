"""Parquet research-dataset uploads go through pyarrow, whose pinned version was raised to a release without the known advisory
(docs/PRODUCTION_SECURITY_REVIEW.md). This exercises the real parser with the installed version; it is skipped, not passed, without pyarrow."""
import io

import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from app.core.errors import ValidationFailedError
from app.services.research_dataset_service import parse_upload


def test_a_parquet_file_round_trips_through_the_upload_parser():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"], "c": [0.5, 1.5, 2.5]})
    buf = io.BytesIO()
    df.to_parquet(buf)
    parsed = parse_upload("data.parquet", buf.getvalue())
    assert parsed.file_type == "parquet" and parsed.dataframe.equals(df)


@pytest.mark.parametrize("content", [b"", b"not a parquet file", b"PAR1" + b"\x00" * 64])
def test_a_corrupt_parquet_file_is_refused_with_a_clean_message(content):
    with pytest.raises(ValidationFailedError, match="Could not parse"):
        parse_upload("bad.parquet", content)
