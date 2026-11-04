#!/usr/bin/env python3
"""Build a privacy-safe source archive for a single Git commit."""

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple


ARCHIVE_PREFIX = "squeezelite-source/"
MANIFEST_NAME = "PUBLIC_SOURCE_MANIFEST.json"
FULL_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
KEY_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".pem", ".key"}
PRIVATE_KEY_RE = re.compile(
    rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"
)
GITHUB_TOKEN_RE = re.compile(
    rb"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{36}|"
    rb"github_pat_[A-Za-z0-9_]{20,})(?![A-Za-z0-9])"
)

# android/python/build is a source package, not generated output.
SOURCE_BUILD_DIR = ("android", "python", "build")


class ExportError(RuntimeError):
    """An expected, user-facing export failure."""


@dataclass
class IncludedFile:
    path: str
    data: bytes
    mode: int
    sha256: str


def validate_relative_path(path: str) -> None:
    """Reject paths that could escape an extraction directory."""

    if not path or path.startswith("/") or "\\" in path:
        raise ExportError("unsafe absolute or ambiguous archive path")
    if re.match(r"^[A-Za-z]:", path):
        raise ExportError("unsafe absolute archive path")

    parts = PurePosixPath(path).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ExportError("unsafe archive path containing '.' or '..'")


def exclusion_reason(path: str) -> Optional[str]:
    """Return why a tracked path must not be published, if it must not."""

    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else path
    lower_name = name.lower()

    if ".git" in parts:
        return "git metadata"
    if lower_name.startswith("bugreport"):
        return "diagnostic bugreport"
    if name == "local.properties":
        return "local configuration"
    if name == "CLAUDE.md":
        return "local agent configuration"
    if lower_name == ".env" or lower_name.startswith(".env."):
        return "environment file"
    if PurePosixPath(name).suffix.lower() in KEY_SUFFIXES:
        return "key material"
    if PurePosixPath(name).suffix.lower() == ".apk":
        return "generated APK"
    if ".gradle" in parts:
        return "generated Gradle data"
    if "__pycache__" in parts:
        return "generated Python cache"

    for index, part in enumerate(parts):
        if part != "build":
            continue
        if tuple(parts[:index + 1]) == SOURCE_BUILD_DIR:
            continue
        return "generated build output"

    return None


def check_for_secrets(data: bytes, path: str) -> None:
    """Fail without exposing secret values if a file contains key material."""

    if PRIVATE_KEY_RE.search(data):
        raise ExportError(
            "secret material detected in {} (private key)".format(path)
        )
    if GITHUB_TOKEN_RE.search(data):
        raise ExportError(
            "secret material detected in {} (GitHub token)".format(path)
        )


def _run_git(repo: Path, args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def find_repo(start: Optional[Path] = None) -> Path:
    """Resolve the work-tree root from the current working directory."""

    cwd = start or Path.cwd()
    result = _run_git(cwd, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        raise ExportError("current directory is not inside a Git work tree")
    return Path(result.stdout.decode("utf-8", "surrogateescape").strip())


def resolve_commit(repo: Path, ref: str) -> str:
    """Resolve and validate a full commit hash."""

    if not FULL_COMMIT_RE.fullmatch(ref):
        raise ExportError("--ref must be a full 40- or 64-character commit SHA")

    result = _run_git(repo, ["rev-parse", "--verify", ref + "^{commit}"])
    if result.returncode != 0:
        raise ExportError("commit not found: {}".format(ref))

    commit = result.stdout.decode("ascii", "strict").strip()
    if commit.lower() != ref.lower():
        raise ExportError("--ref must identify a commit directly")
    return commit


def _relative_archive_path(member: tarfile.TarInfo) -> Optional[str]:
    root_prefix = ARCHIVE_PREFIX.rstrip("/")
    if member.name == root_prefix and member.isdir():
        return None
    if not member.name.startswith(ARCHIVE_PREFIX):
        raise ExportError(
            "archive member is outside the expected prefix: {}".format(
                member.name
            )
        )

    relative = member.name[len(ARCHIVE_PREFIX):]
    if not relative and member.isdir():
        return None
    validate_relative_path(relative.rstrip("/"))
    return relative.rstrip("/")


def _validate_member_type(member: tarfile.TarInfo, path: str) -> None:
    if member.issym():
        raise ExportError("symlink is not allowed in source archive: {}".format(path))
    if member.islnk():
        raise ExportError("hardlink is not allowed in source archive: {}".format(path))
    if not (member.isreg() or member.isdir()):
        raise ExportError("special file is not allowed in source archive: {}".format(path))


def _read_archive(
    archive_path: Path,
) -> Tuple[List[IncludedFile], List[Dict[str, str]]]:
    included: List[IncludedFile] = []
    excluded: List[Dict[str, str]] = []

    with tarfile.open(str(archive_path), mode="r:") as archive:
        for member in archive:
            path = _relative_archive_path(member)
            if path is None:
                continue
            _validate_member_type(member, path)
            if member.isdir():
                continue

            reason = exclusion_reason(path)
            if reason is not None:
                excluded.append({"path": path, "reason": reason})
                continue

            source = archive.extractfile(member)
            if source is None:
                raise ExportError("could not read archive member: {}".format(path))
            data = source.read()
            if len(data) != member.size:
                raise ExportError("truncated archive member: {}".format(path))

            check_for_secrets(data, path)
            included.append(
                IncludedFile(
                    path=path,
                    data=data,
                    mode=member.mode & 0o777,
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )

    included.sort(key=lambda entry: entry.path)
    excluded.sort(key=lambda entry: entry["path"])
    return included, excluded


def _manifest_bytes(
    commit: str, included: Iterable[IncludedFile], excluded: List[Dict[str, str]]
) -> bytes:
    manifest = {
        "commit": commit,
        "archive_prefix": ARCHIVE_PREFIX,
        "files": [
            {
                "path": entry.path,
                "sha256": entry.sha256,
                "size": len(entry.data),
            }
            for entry in included
        ],
        "excluded": excluded,
    }
    return (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_archive(
    included: List[IncludedFile],
    manifest: bytes,
    archive_temp_path: Path,
) -> None:
    with open(str(archive_temp_path), "wb") as raw_output:
        gzip_output = gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_output, mtime=0
        )
        try:
            with tarfile.open(fileobj=gzip_output, mode="w") as archive:
                for entry in included:
                    info = tarfile.TarInfo(
                        name=ARCHIVE_PREFIX + entry.path
                    )
                    info.size = len(entry.data)
                    info.mode = entry.mode
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    archive.addfile(info, BytesIO(entry.data))

                info = tarfile.TarInfo(
                    name=ARCHIVE_PREFIX + MANIFEST_NAME
                )
                info.size = len(manifest)
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                archive.addfile(info, BytesIO(manifest))
        finally:
            gzip_output.close()


def export_public_source(ref: str, output: str, cwd: Optional[Path] = None) -> Path:
    """Export one commit to a filtered, manifest-bearing source tarball."""

    if not os.path.isabs(output):
        raise ExportError("--output must be an absolute path")
    if os.path.lexists(output):
        raise ExportError("refusing to overwrite existing output: {}".format(output))

    output_path = Path(output)
    output_dir = output_path.parent
    if not output_dir.is_dir():
        raise ExportError("output directory does not exist: {}".format(output_dir))

    repo = find_repo(cwd)
    commit = resolve_commit(repo, ref)

    with tempfile.TemporaryDirectory(
        prefix=".export-public-source-", dir=str(output_dir)
    ) as temp_dir:
        temp_path = Path(temp_dir)
        git_archive_path = temp_path / "source.tar"

        with open(str(git_archive_path), "wb") as archive_file:
            result = subprocess.run(
                [
                    "git",
                    "archive",
                    "--format=tar",
                    "--prefix=" + ARCHIVE_PREFIX,
                    commit,
                ],
                cwd=str(repo),
                stdout=archive_file,
                stderr=subprocess.PIPE,
                check=False,
            )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", "replace").strip()
            raise ExportError(
                "git archive failed for {}: {}".format(commit, message)
            )

        included, excluded = _read_archive(git_archive_path)
        manifest = _manifest_bytes(commit, included, excluded)

        fd, temp_output_name = tempfile.mkstemp(
            prefix=".{}-".format(output_path.name),
            suffix=".tmp",
            dir=str(output_dir),
        )
        os.close(fd)
        temp_output_path = Path(temp_output_name)
        try:
            _write_archive(included, manifest, temp_output_path)
            os.chmod(str(temp_output_path), 0o644)
            try:
                os.link(str(temp_output_path), str(output_path))
            except FileExistsError:
                raise ExportError(
                    "refusing to overwrite existing output: {}".format(output)
                )
            except OSError as error:
                raise ExportError(
                    "could not create output atomically: {}".format(error)
                )
        finally:
            try:
                temp_output_path.unlink()
            except FileNotFoundError:
                pass

    return output_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export a privacy-safe Squeezelite source snapshot."
    )
    parser.add_argument("--ref", required=True, help="full commit SHA")
    parser.add_argument(
        "--output", required=True, help="absolute output .tar.gz path"
    )
    args = parser.parse_args(argv)

    try:
        output = export_public_source(args.ref, args.output)
    except ExportError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1

    print("wrote {}".format(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
