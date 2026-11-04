import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "export_public_source.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location(
        "export_public_source", str(SCRIPT)
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExportPublicSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def git(self, repo, *args):
        return subprocess.run(
            ["git"] + list(args),
            cwd=str(repo),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def new_repo(self):
        repo = self.root / "repo"
        repo.mkdir()
        self.git(repo, "init", "-q")
        self.git(repo, "config", "user.email", "test@example.invalid")
        self.git(repo, "config", "user.name", "Test User")
        return repo

    def write(self, repo, path, data):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            target.write_bytes(data)
        else:
            target.write_text(data, encoding="utf-8")
        return target

    def commit(self, repo, message):
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", message)
        return self.git(repo, "rev-parse", "HEAD").stdout.strip()

    def export(self, repo, commit, output):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--ref",
                commit,
                "--output",
                str(output),
            ],
            cwd=str(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_keeps_source_and_excludes_private_or_generated_files(self):
        repo = self.new_repo()
        self.write(repo, "main.c", "int main(void) { return 0; }\n")
        self.write(
            repo,
            "android/app/src/main/java/example/Main.java",
            "class Main {}\n",
        )
        self.write(repo, "android/build.gradle", "// build\n")
        self.write(
            repo,
            "android/python/build/project.py",
            "SOURCE_BUILD_INPUT = True\n",
        )
        self.write(repo, "bugreport-device.zip", b"diagnostic")
        self.write(repo, "nested/bugreport-old.log", "diagnostic")
        self.write(repo, "android/app/local.properties", "sdk.dir=/local\n")
        self.write(repo, "CLAUDE.md", "local instructions\n")
        self.write(repo, ".env.local", "TOKEN=local\n")
        self.write(repo, "keys/release.jks", b"not a real key")
        self.write(repo, "android/app/build/outputs/app-debug.apk", b"apk")
        self.write(repo, "android/app/build/generated.txt", "generated")
        self.write(repo, "android/.gradle/cache.bin", "generated")
        self.write(repo, "tools/__pycache__/cache.pyc", "generated")
        commit = self.commit(repo, "fixture")

        output = self.root / "source.tar.gz"
        result = self.export(repo, commit, output)
        self.assertEqual(result.returncode, 0, result.stderr)

        with tarfile.open(str(output), "r:gz") as archive:
            names = set(archive.getnames())
            manifest_bytes = archive.extractfile(
                "squeezelite-source/PUBLIC_SOURCE_MANIFEST.json"
            ).read()

        expected = {
            "squeezelite-source/main.c",
            "squeezelite-source/android/app/src/main/java/example/Main.java",
            "squeezelite-source/android/build.gradle",
            "squeezelite-source/android/python/build/project.py",
        }
        self.assertTrue(expected.issubset(names))
        forbidden = {
            "squeezelite-source/bugreport-device.zip",
            "squeezelite-source/nested/bugreport-old.log",
            "squeezelite-source/android/app/local.properties",
            "squeezelite-source/CLAUDE.md",
            "squeezelite-source/.env.local",
            "squeezelite-source/keys/release.jks",
            "squeezelite-source/android/app/build/outputs/app-debug.apk",
            "squeezelite-source/android/app/build/generated.txt",
            "squeezelite-source/android/.gradle/cache.bin",
            "squeezelite-source/tools/__pycache__/cache.pyc",
        }
        self.assertTrue(forbidden.isdisjoint(names))
        self.assertNotIn("squeezelite-source/.git/HEAD", names)

        manifest = json.loads(manifest_bytes.decode("utf-8"))
        self.assertEqual(manifest["commit"], commit)
        files = {entry["path"]: entry for entry in manifest["files"]}
        self.assertEqual(
            files["main.c"]["sha256"],
            hashlib.sha256(b"int main(void) { return 0; }\n").hexdigest(),
        )
        self.assertIn("android/python/build/project.py", files)
        excluded = {entry["path"] for entry in manifest["excluded"]}
        self.assertTrue(
            {
                "bugreport-device.zip",
                "nested/bugreport-old.log",
                "android/app/local.properties",
                "CLAUDE.md",
                ".env.local",
                "keys/release.jks",
                "android/app/build/outputs/app-debug.apk",
                "android/app/build/generated.txt",
                "android/.gradle/cache.bin",
                "tools/__pycache__/cache.pyc",
            }.issubset(excluded)
        )
        self.assertNotIn(str(self.root), manifest_bytes.decode("utf-8"))

    def test_old_commit_with_tracked_bugreport_is_safe(self):
        repo = self.new_repo()
        self.write(repo, "bugreport-old.zip", b"diagnostic")
        self.write(repo, "main.c", "old source\n")
        old_commit = self.commit(repo, "old commit with diagnostic")

        (repo / "bugreport-old.zip").unlink()
        self.write(repo, "main.c", "new source\n")
        self.commit(repo, "remove diagnostic")

        output = self.root / "old-source.tar.gz"
        result = self.export(repo, old_commit, output)
        self.assertEqual(result.returncode, 0, result.stderr)

        with tarfile.open(str(output), "r:gz") as archive:
            names = set(archive.getnames())
        self.assertIn("squeezelite-source/main.c", names)
        self.assertNotIn("squeezelite-source/bugreport-old.zip", names)

    def test_github_token_in_normal_file_fails_without_echoing_value(self):
        repo = self.new_repo()
        token = "gh" + "p_" + ("A" * 36)
        self.write(repo, "src/notes.txt", "credential=" + token + "\n")
        commit = self.commit(repo, "fixture with synthetic token")

        output = self.root / "source.tar.gz"
        result = self.export(repo, commit, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("src/notes.txt", result.stderr)
        self.assertNotIn(token, result.stdout)
        self.assertNotIn(token, result.stderr)
        self.assertFalse(output.exists())

    def test_private_key_material_is_rejected_without_echoing_value(self):
        exporter = load_exporter()
        marker = "-----" + "BEGIN " + "RSA " + "PRIVATE KEY" + "-----"
        content = (marker + "\nnot-real-key-data\n").encode("ascii")
        with self.assertRaises(exporter.ExportError) as raised:
            exporter.check_for_secrets(content, "src/normal-name.txt")
        self.assertIn("private key", str(raised.exception))
        self.assertNotIn(marker, str(raised.exception))

    def test_rejects_unsafe_paths_hardlinks_and_special_files(self):
        exporter = load_exporter()
        for path in (
            "/etc/passwd",
            "../outside",
            "a/../../outside",
            "C:/outside",
            "a\\outside",
        ):
            with self.subTest(path=path):
                with self.assertRaises(exporter.ExportError):
                    exporter.validate_relative_path(path)

        hardlink = tarfile.TarInfo("squeezelite-source/link")
        hardlink.type = tarfile.LNKTYPE
        hardlink.linkname = "squeezelite-source/main.c"
        with self.assertRaises(exporter.ExportError):
            exporter._validate_member_type(hardlink, "link")

        special = tarfile.TarInfo("squeezelite-source/fifo")
        special.type = tarfile.FIFOTYPE
        with self.assertRaises(exporter.ExportError):
            exporter._validate_member_type(special, "fifo")

    def test_rejects_symlink_in_source(self):
        repo = self.new_repo()
        self.write(repo, "main.c", "source\n")
        os.symlink("main.c", repo / "linked.c")
        commit = self.commit(repo, "fixture with symlink")

        output = self.root / "source.tar.gz"
        result = self.export(repo, commit, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertFalse(output.exists())

    def test_refuses_to_overwrite_existing_file_or_symlink(self):
        repo = self.new_repo()
        self.write(repo, "main.c", "source\n")
        commit = self.commit(repo, "fixture")

        output = self.root / "source.tar.gz"
        output.write_bytes(b"keep me")
        result = self.export(repo, commit, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), b"keep me")

        target = self.root / "target.tar.gz"
        target.write_bytes(b"target")
        link = self.root / "linked-output.tar.gz"
        os.symlink(target, link)
        result = self.export(repo, commit, link)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_bytes(), b"target")


if __name__ == "__main__":
    unittest.main()
