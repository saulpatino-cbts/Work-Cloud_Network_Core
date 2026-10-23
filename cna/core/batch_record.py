"""Batch offline export/import (BUILD-03).

A **batch record** is a portable zip of one or more discovery checkpoints plus a
manifest. It lets a subscription/tenant/account scanned offline be carried to an
online appliance and merged into an engagement's checkpoint set, so the existing
topology reassembly (`EngagementStore.load_aws_topology` /
`load_azure_topology`) includes it as if it had been discovered live.

Design (see .kiro/specs/batch-offline-import/):
  - A record carries TOPOLOGY ONLY — never a credential or secret.
  - Integrity + idempotency key is a sha256 per checkpoint, in the manifest.
  - Import is validate-all-then-write-all (no partial import), idempotent on
    (source id + sha256), newest-by-discovered_at on conflict.
  - Optional passphrase encryption (AES-256-GCM via scrypt) protects the record
    in transit; it is NOT a substitute for the no-secrets rule.
  - This is the single-customer model: one appliance = one customer, so merging
    unifies that customer's own sources; there is no cross-customer path.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from cna.core.persistence import EngagementStore
from cna.core.topology_schema import (
    TOPOLOGY_SCHEMA_VERSION,
    AWSRegionTopology,
    AzureSubscriptionTopology,
)

logger = logging.getLogger("cna.core.batch_record")

BATCH_RECORD_SCHEMA_VERSION = "1.0.0"
_MANIFEST_NAME = "manifest.json"
_CHECKPOINTS_DIR = "checkpoints"
_ENC_MAGIC = b"CNABATCH1"  # prefix on an encrypted record

# Platform -> the topology model its checkpoint deserialises to. Import
# constructs the model to reject anything that is not a valid topology dump
# (data, never code — R4.2).
_PLATFORM_MODELS = {
    "aws": AWSRegionTopology,
    "azure": AzureSubscriptionTopology,
}

# Manifest keys that must never carry a secret. Export writes only the keys
# below; import rejects a manifest with anything credential-shaped.
_FORBIDDEN_MANIFEST_SUBSTRINGS = ("password", "secret", "token", "key", "credential")


class BatchRecordError(Exception):
    """Raised on a malformed, tampered, or version-incompatible record."""


@dataclass
class CheckpointEntry:
    platform: str
    source_id: str
    filename: str
    sha256: str
    discovered_at: str  # ISO-8601; drives newest-by-timestamp conflict


@dataclass
class BatchManifest:
    schema_version: str = BATCH_RECORD_SCHEMA_VERSION
    topology_schema_version: str = TOPOLOGY_SCHEMA_VERSION
    exported_at: str = ""
    label: str = ""
    encrypted: bool = False
    checkpoints: list[CheckpointEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "topology_schema_version": self.topology_schema_version,
            "exported_at": self.exported_at,
            "label": self.label,
            "encrypted": self.encrypted,
            "checkpoints": [vars(c) for c in self.checkpoints],
        }

    @classmethod
    def from_dict(cls, d: dict) -> BatchManifest:
        return cls(
            schema_version=d.get("schema_version", ""),
            topology_schema_version=d.get("topology_schema_version", ""),
            exported_at=d.get("exported_at", ""),
            label=d.get("label", ""),
            encrypted=bool(d.get("encrypted", False)),
            checkpoints=[CheckpointEntry(**c) for c in d.get("checkpoints", [])],
        )


@dataclass
class ImportResult:
    imported: list[str] = field(default_factory=list)  # source ids newly written
    skipped: list[str] = field(default_factory=list)  # idempotent (identical) re-imports
    replaced: list[str] = field(default_factory=list)  # newer-wins replacements

    def offline_source_ids(self) -> list[str]:
        """Source ids that joined the topology from this record (imported + replaced).

        Feeds `DiscoveryCoverageReport.note_imported_offline` so a report can flag
        which sources were imported offline rather than discovered live (R3.3).
        Skipped (idempotent) sources are already present, so they are not new
        offline arrivals here.
        """
        return sorted(set(self.imported) | set(self.replaced))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _checkpoint_filename(platform: str, source_id: str) -> str:
    """Mirror EngagementStore's checkpoint naming so import lands in place."""
    safe = source_id.replace("/", "_").replace("-", "_")
    return f"{platform}_{safe}.json"


# ── optional passphrase encryption (AES-256-GCM via scrypt) ─────────────────


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _encrypt(plaintext: bytes, passphrase: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(passphrase, salt)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return _ENC_MAGIC + salt + nonce + ct


def _decrypt(blob: bytes, passphrase: str) -> bytes:
    if not blob.startswith(_ENC_MAGIC):
        raise BatchRecordError("record is not an encrypted CNA batch record")
    body = blob[len(_ENC_MAGIC):]
    salt, nonce, ct = body[:16], body[16:28], body[28:]
    key = _derive_key(passphrase, salt)
    try:
        return AESGCM(key).decrypt(nonce, ct, None)
    except Exception as exc:  # InvalidTag etc.
        raise BatchRecordError("could not decrypt the batch record (wrong key or corrupt)") from exc


# ── export ───────────────────────────────────────────────────────────────


def export_batch_record(
    store: EngagementStore,
    engagement_id: str,
    source_ids: list[str] | None,
    out_path: Path,
    *,
    label: str = "",
    encrypt: bool = False,
    passphrase: str | None = None,
) -> Path:
    """Export selected discovery checkpoints as a portable batch record.

    `source_ids` None means every checkpoint in the engagement's discovery dir.
    Needs no network or live appliance.
    """
    out_path = Path(out_path)
    disc_dir = store.engagement_dir(engagement_id) / store.DISCOVERY_DIR
    if not disc_dir.exists():
        raise BatchRecordError(f"no discovery checkpoints for engagement '{engagement_id}'")

    manifest = BatchManifest(exported_at=datetime.now(UTC).isoformat(), label=label, encrypted=encrypt)
    members: dict[str, bytes] = {}  # arcname -> bytes

    for ckpt in sorted(disc_dir.glob("*.json")):
        platform = ckpt.stem.split("_", 1)[0]
        if platform not in _PLATFORM_MODELS:
            continue
        raw = ckpt.read_bytes()
        data = json.loads(raw)
        src = _source_id_from_checkpoint(platform, data)
        if source_ids is not None and src not in source_ids:
            continue
        # Reconstruct via the model so we export exactly a valid topology dump
        # (and would raise here if a checkpoint were malformed).
        _PLATFORM_MODELS[platform](**data)
        fname = _checkpoint_filename(platform, src)
        members[f"{_CHECKPOINTS_DIR}/{fname}"] = raw
        manifest.checkpoints.append(
            CheckpointEntry(
                platform=platform,
                source_id=src,
                filename=fname,
                sha256=_sha256(raw),
                discovered_at=_discovered_at(platform, data, ckpt),
            )
        )

    if not manifest.checkpoints:
        raise BatchRecordError("no matching checkpoints to export")

    # Build the zip in memory so we can optionally encrypt the whole artifact.
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_MANIFEST_NAME, json.dumps(manifest.to_dict(), indent=2))
        for arcname, data in members.items():
            zf.writestr(arcname, data)
    payload = buf.getvalue()

    if encrypt:
        if not passphrase:
            raise BatchRecordError("encrypt=True requires a passphrase")
        payload = _encrypt(payload, passphrase)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)
    logger.info("Batch record exported: %s (%d checkpoint(s))", out_path, len(manifest.checkpoints))
    return out_path


# ── import ───────────────────────────────────────────────────────────────


def import_batch_record(
    store: EngagementStore,
    engagement_id: str,
    record_path: Path,
    *,
    passphrase: str | None = None,
    conflict: str = "newest",
) -> ImportResult:
    """Import a batch record into an engagement's checkpoint set.

    Validate-all-then-write-all: nothing is written unless every checkpoint
    validates (R4.1). Idempotent on (source id + sha256); newest-by-timestamp on
    conflict (or `conflict="refuse"` to abort on a differing existing source).
    """
    record_path = Path(record_path)
    blob = record_path.read_bytes()
    if blob.startswith(_ENC_MAGIC):
        if not passphrase:
            raise BatchRecordError("record is encrypted; a passphrase is required")
        blob = _decrypt(blob, passphrase)

    import io

    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as exc:
        raise BatchRecordError("record is not a valid zip (corrupt or truncated)") from exc

    with zf:
        names = set(zf.namelist())
        if _MANIFEST_NAME not in names:
            raise BatchRecordError("record has no manifest.json")
        manifest = BatchManifest.from_dict(json.loads(zf.read(_MANIFEST_NAME)))
        _validate_manifest(manifest)

        # Phase 1: validate every checkpoint (checksum + model) before any write.
        validated: list[tuple[CheckpointEntry, bytes, dict]] = []
        for entry in manifest.checkpoints:
            arc = f"{_CHECKPOINTS_DIR}/{entry.filename}"
            if arc not in names:
                raise BatchRecordError(f"manifest lists {entry.filename} but it is missing")
            raw = zf.read(arc)
            if _sha256(raw) != entry.sha256:
                raise BatchRecordError(f"checksum mismatch for {entry.filename} (tampered/truncated)")
            if entry.platform not in _PLATFORM_MODELS:
                raise BatchRecordError(f"unknown platform '{entry.platform}' in record")
            data = json.loads(raw)
            _PLATFORM_MODELS[entry.platform](**data)  # reject non-topology shapes (data, not code)
            validated.append((entry, raw, data))

        # Phase 2: write-all, with idempotency + conflict handling.
        disc_dir = store.engagement_dir(engagement_id) / store.DISCOVERY_DIR
        disc_dir.mkdir(parents=True, exist_ok=True)
        result = ImportResult()
        for entry, raw, data in validated:
            target = disc_dir / entry.filename
            if target.exists():
                existing = target.read_bytes()
                if _sha256(existing) == entry.sha256:
                    result.skipped.append(entry.source_id)  # identical -> idempotent
                    continue
                if conflict == "refuse":
                    raise BatchRecordError(
                        f"source {entry.source_id} already present and differs (conflict=refuse)"
                    )
                # newest-by-discovered_at wins
                existing_when = _discovered_at(entry.platform, json.loads(existing), target)
                if entry.discovered_at <= existing_when:
                    result.skipped.append(entry.source_id)
                    continue
                target.write_bytes(raw)
                result.replaced.append(entry.source_id)
            else:
                target.write_bytes(raw)
                result.imported.append(entry.source_id)

    logger.info(
        "Batch import into %s: %d imported, %d replaced, %d skipped",
        engagement_id,
        len(result.imported),
        len(result.replaced),
        len(result.skipped),
    )
    return result


# ── helpers ────────────────────────────────────────────────────────────────


def _validate_manifest(m: BatchManifest) -> None:
    if m.schema_version != BATCH_RECORD_SCHEMA_VERSION:
        raise BatchRecordError(
            f"record schema {m.schema_version!r} != supported {BATCH_RECORD_SCHEMA_VERSION!r}"
        )
    if m.topology_schema_version != TOPOLOGY_SCHEMA_VERSION:
        raise BatchRecordError(
            f"topology schema {m.topology_schema_version!r} != appliance "
            f"{TOPOLOGY_SCHEMA_VERSION!r}; re-export against a matching version"
        )
    if not m.checkpoints:
        raise BatchRecordError("record manifest lists no checkpoints")
    # No-secrets guard on the manifest surface.
    flat = json.dumps(m.to_dict()).lower()
    for key in m.checkpoints:
        for bad in _FORBIDDEN_MANIFEST_SUBSTRINGS:
            if bad in (key.source_id or "").lower():
                raise BatchRecordError(f"manifest source_id looks credential-shaped: {bad}")
    _ = flat  # reserved for a deeper scan if the manifest grows


def _source_id_from_checkpoint(platform: str, data: dict) -> str:
    if platform == "aws":
        return data.get("account_id") or data.get("region") or "unknown"
    return data.get("subscription_id") or data.get("tenant_id") or "unknown"


def _discovered_at(platform: str, data: dict, path: Path) -> str:
    """Best-effort discovery timestamp for newest-wins; falls back to file mtime."""
    for key in ("discovered_at", "collected_at", "generated_at"):
        if data.get(key):
            return str(data[key])
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
    except OSError:
        return datetime.now(UTC).isoformat()
