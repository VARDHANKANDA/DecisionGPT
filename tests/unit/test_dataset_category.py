from app.services import dataset_category as dc


def test_classify_from_source_strings():
    assert dc.classify(source="RETIRED_NON_INDIAN_BENCHMARK - External Benchmark - M5") == dc.RETIRED_NON_INDIAN
    assert dc.classify(evidence_level="SYNTHETIC") == dc.SYNTHETIC_CONTROLLED
    assert dc.classify(source="External Benchmark - India Agri-Commodity ... AGMARKNET") == dc.INDIA_AGRICULTURAL_PRICE
    assert dc.classify(explicit="INDIA_AGRICULTURAL_PRICE") == dc.INDIA_AGRICULTURAL_PRICE
    assert dc.classify(source="holidays lib festival calendar", explicit="INDIA_PUBLIC_CONTEXT") == dc.INDIA_PUBLIC_CONTEXT
    assert dc.classify(source="RBI policy repo rate context") == dc.INDIA_PUBLIC_CONTEXT
    assert dc.classify(source="External Benchmark - India retail transactions (data_type=real)") == dc.INDIA_REAL_BUSINESS
    assert dc.classify(source="External Benchmark - something (data_type=real)") == dc.EXTERNAL_BENCHMARK
    assert dc.classify(source="a private upload") == dc.UNCLASSIFIED


def test_explicit_always_wins():
    assert dc.classify(source="synthetic something", explicit="INDIA_PUBLIC_CONTEXT") == "INDIA_PUBLIC_CONTEXT"
