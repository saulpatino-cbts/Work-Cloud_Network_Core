"""Unit tests for cna.diagram_engine.shape_catalog."""

from __future__ import annotations

from cna.diagram_engine.shape_catalog import (
    ALLOWED_LIBS,
    catalog_snapshot,
    is_allowed_style,
    shape_style,
)


def test_allowed_libs_is_azure2_and_aws4():
    assert ALLOWED_LIBS == frozenset({"azure2", "aws4"})


def test_is_allowed_style_accepts_pinned_libraries():
    assert is_allowed_style("shape=mxgraph.azure2.virtual_networks;")
    assert is_allowed_style("shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.vpc;")


def test_is_allowed_style_rejects_other_libraries():
    assert not is_allowed_style("shape=mxgraph.azure.virtual_networks;")  # azure (v1)
    assert not is_allowed_style("shape=mxgraph.aws3.vpc;")
    assert not is_allowed_style("shape=mxgraph.gcp2.network;")
    assert not is_allowed_style("")
    assert not is_allowed_style("rounded=1;")


def test_shape_style_returns_catalog_entry():
    style = shape_style("aws4", "vpc")
    assert "mxgraph.aws4" in style


def test_shape_style_returns_default_when_missing():
    fallback = "shape=mxgraph.azure2.placeholder;"
    assert shape_style("azure2", "does_not_exist", fallback) == fallback


def test_shape_style_rejects_unknown_library():
    fallback = "shape=mxgraph.azure2.placeholder;"
    assert shape_style("gcp2", "anything", fallback) == fallback


def test_catalog_snapshot_only_pinned_libraries():
    snap = catalog_snapshot()
    assert set(snap.keys()) == {"azure2", "aws4"}
    for lib, table in snap.items():
        for key, style in table.items():
            assert is_allowed_style(style), f"{lib}:{key} = {style}"
