"""Unit tests for cna.core.batch_record (BUILD-03).

Synthetic checkpoints only — no cloud, no network. Covers export/import
round-trip, idempotency, newest-by-timestamp conflict, integrity (tampered /
truncated refused with no partial write), schema guard, no-secrets, and the
optional passphrase encryption round-trip.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from cna.core.batch_record import (
    BatchRecordError,
    export_batch_record,
    import_batch_record,
)
from cna.core.persistence import EngagementStore
from cna.core.topology_schema import TOPOLOGY_SCHEMA_VERSION


def _store(tmp_path: Path) -> EngagementStore:
    return EngagementStore(data_dir=tmp_path)


def _write_checkpoint(store, eng, platform, data) -> Path:
    return store.write_discovery_checkpoint(
        eng, platform, data.get("account_id") or data["subscription_id"], data
    )


def _aws_ckpt(account_id="123456789012", region="us-east-1", discovered_at="2026-10-01T00:00:00Z"):
    return {"account_id": account_id, "region": region, "discovered_at": discovered_at}


def _azure_ckpt(sub_id="sub-1", tenant="ten-1", discovered_at="2026-10-01T00:00:00Z"):
    return {
        "subscription_id": sub_id,
        "subscription_name": "s",
        "tenant_id": tenant,
        "discovered_at": discovered_at,
    }


class TestRoundTrip:
    def test_export_then_import_into_fresh_store(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt())
        _write_checkpoint(src, "eng-a", "azure", _azure_ckpt())
        rec = export_batch_record(src, "eng-a", None, tmp_path / "rec.zip", label="cust")
        assert rec.is_file()

        dst = _store(tmp_path / "dst")
        result = import_batch_record(dst, "eng-b", rec)
        assert sorted(result.imported) == ["123456789012", "sub-1"]
        # reassembly picks them up as if discovered live
        aws = dst.load_aws_topology("eng-b")
        azure = dst.load_azure_topology("eng-b")
        assert aws.regions[0].account_id == "123456789012"
        assert azure.subscriptions[0].subscription_id == "sub-1"

    def test_export_selected_source_only(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt("111111111111"))
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt("222222222222"))
        rec = export_batch_record(src, "eng-a", ["111111111111"], tmp_path / "rec.zip")
        with zipfile.ZipFile(rec) as zf:
            manifest = json.loads(zf.read("manifest.json"))
        ids = [c["source_id"] for c in manifest["checkpoints"]]
        assert ids == ["111111111111"]


class TestIdempotencyAndConflict:
    def test_reimport_same_record_is_idempotent(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt())
        rec = export_batch_record(src, "eng-a", None, tmp_path / "rec.zip")
        dst = _store(tmp_path / "dst")
        import_batch_record(dst, "eng-b", rec)
        second = import_batch_record(dst, "eng-b", rec)
        assert second.imported == []
        assert second.skipped == ["123456789012"]
        # exactly one checkpoint on disk
        disc = tmp_path / "dst" / "eng-b" / "discovery"
        assert len(list(disc.glob("aws_*.json"))) == 1

    def test_newer_wins_on_conflict(self, tmp_path):
        dst = _store(tmp_path / "dst")
        _write_checkpoint(dst, "eng-b", "aws", _aws_ckpt(discovered_at="2026-01-01T00:00:00Z"))
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt(discovered_at="2026-10-01T00:00:00Z"))
        rec = export_batch_record(src, "eng-a", None, tmp_path / "rec.zip")
        result = import_batch_record(dst, "eng-b", rec, conflict="newest")
        assert result.replaced == ["123456789012"]
        loaded = json.loads(
            (tmp_path / "dst" / "eng-b" / "discovery" / "aws_123456789012.json").read_text()
        )
        assert loaded["discovered_at"] == "2026-10-01T00:00:00Z"

    def test_older_does_not_replace(self, tmp_path):
        dst = _store(tmp_path / "dst")
        _write_checkpoint(dst, "eng-b", "aws", _aws_ckpt(discovered_at="2026-10-01T00:00:00Z"))
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt(discovered_at="2026-01-01T00:00:00Z"))
        rec = export_batch_record(src, "eng-a", None, tmp_path / "rec.zip")
        result = import_batch_record(dst, "eng-b", rec, conflict="newest")
        assert result.skipped == ["123456789012"]

    def test_refuse_conflict_aborts(self, tmp_path):
        dst = _store(tmp_path / "dst")
        _write_checkpoint(dst, "eng-b", "aws", _aws_ckpt(discovered_at="2026-01-01T00:00:00Z"))
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt(discovered_at="2026-10-01T00:00:00Z"))
        rec = export_batch_record(src, "eng-a", None, tmp_path / "rec.zip")
        with pytest.raises(BatchRecordError):
            import_batch_record(dst, "eng-b", rec, conflict="refuse")


class TestIntegrity:
    def _tamper(self, rec: Path) -> Path:
        with zipfile.ZipFile(rec) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        # corrupt a checkpoint body without updating the manifest checksum
        ckpt_name = next(n for n in members if n.startswith("checkpoints/"))
        members[ckpt_name] = members[ckpt_name] + b" "
        out = rec.with_name("tampered.zip")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for n, d in members.items():
                zf.writestr(n, d)
        out.write_bytes(buf.getvalue())
        return out

    def test_tampered_checksum_refused_no_partial_write(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt())
        _write_checkpoint(src, "eng-a", "azure", _azure_ckpt())
        rec = export_batch_record(src, "eng-a", None, tmp_path / "rec.zip")
        tampered = self._tamper(rec)
        dst = _store(tmp_path / "dst")
        with pytest.raises(BatchRecordError):
            import_batch_record(dst, "eng-b", tampered)
        # validate-all-then-write-all: NOTHING written on failure
        disc = tmp_path / "dst" / "eng-b" / "discovery"
        assert not disc.exists() or not list(disc.glob("*.json"))

    def test_truncated_zip_refused(self, tmp_path):
        bad = tmp_path / "bad.zip"
        bad.write_bytes(b"not a zip at all")
        dst = _store(tmp_path / "dst")
        with pytest.raises(BatchRecordError):
            import_batch_record(dst, "eng-b", bad)


class TestSchemaGuard:
    def test_incompatible_schema_refused(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt())
        rec = export_batch_record(src, "eng-a", None, tmp_path / "rec.zip")
        # rewrite the manifest with a bad schema version
        with zipfile.ZipFile(rec) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        m = json.loads(members["manifest.json"])
        m["schema_version"] = "9.9.9"
        members["manifest.json"] = json.dumps(m).encode()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for n, d in members.items():
                zf.writestr(n, d)
        rec.write_bytes(buf.getvalue())
        dst = _store(tmp_path / "dst")
        with pytest.raises(BatchRecordError):
            import_batch_record(dst, "eng-b", rec)

    def test_topology_schema_version_recorded(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt())
        rec = export_batch_record(src, "eng-a", None, tmp_path / "rec.zip")
        with zipfile.ZipFile(rec) as zf:
            m = json.loads(zf.read("manifest.json"))
        assert m["topology_schema_version"] == TOPOLOGY_SCHEMA_VERSION


class TestEncryption:
    def test_encrypt_roundtrip(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt())
        rec = export_batch_record(
            src, "eng-a", None, tmp_path / "rec.enc", encrypt=True, passphrase="pw"
        )
        # encrypted: the magic-prefixed blob is not a valid zip
        with pytest.raises(zipfile.BadZipFile):
            zipfile.ZipFile(rec)
        dst = _store(tmp_path / "dst")
        result = import_batch_record(dst, "eng-b", rec, passphrase="pw")
        assert result.imported == ["123456789012"]

    def test_wrong_passphrase_fails(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt())
        rec = export_batch_record(
            src, "eng-a", None, tmp_path / "rec.enc", encrypt=True, passphrase="right"
        )
        dst = _store(tmp_path / "dst")
        with pytest.raises(BatchRecordError):
            import_batch_record(dst, "eng-b", rec, passphrase="wrong")

    def test_encrypted_without_passphrase_refused(self, tmp_path):
        src = _store(tmp_path / "src")
        _write_checkpoint(src, "eng-a", "aws", _aws_ckpt())
        rec = export_batch_record(
            src, "eng-a", None, tmp_path / "rec.enc", encrypt=True, passphrase="pw"
        )
        dst = _store(tmp_path / "dst")
        with pytest.raises(BatchRecordError):
            import_batch_record(dst, "eng-b", rec)


class TestEmpty:
    def test_export_with_no_checkpoints_errors(self, tmp_path):
        src = _store(tmp_path / "src")
        src.engagement_dir("eng-a").mkdir(parents=True)
        (src.engagement_dir("eng-a") / "discovery").mkdir()
        with pytest.raises(BatchRecordError):
            export_batch_record(src, "eng-a", None, tmp_path / "rec.zip")
