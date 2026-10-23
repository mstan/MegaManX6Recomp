"""Exercise actual Git dirty/edit/delete and normalized cache provenance."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def run(*args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT)


def main():
    script = Path(__file__).with_name("mmx6_build_provenance.py")
    with tempfile.TemporaryDirectory(prefix="mmx6-provenance-") as temp:
        root = Path(temp)
        repo = root / "repo"
        repo.mkdir()
        run("git", "-C", str(repo), "init", "--quiet")
        run("git", "-C", str(repo), "config", "user.name", "Manifest fixture")
        run("git", "-C", str(repo), "config", "user.email", "manifest@example.invalid")
        tracked = repo / "plugin.inc"
        tracked.write_text("original\n")
        run("git", "-C", str(repo), "add", "plugin.inc")
        run("git", "-C", str(repo), "commit", "--quiet", "-m", "fixture")

        def collect(path):
            cache = path / "cache.txt"
            cache.write_text("PLUGIN_OPTION:STRING=1\nROOT:PATH=" + path.as_posix() + "\n")
            output = path / "provenance.json"
            run(sys.executable, str(script), "--root", "game=" + str(path),
                "--repository", "game=" + str(path), "--cache", str(cache), "--output", str(output))
            return json.loads(output.read_text())

        clean = collect(repo)
        tracked.write_text("changed implementation\n")
        dirty = collect(repo)
        assert clean != dirty
        assert clean["repositories"]["game"]["head"] == dirty["repositories"]["game"]["head"]
        assert "plugin.inc" in dirty["repositories"]["game"]["tracked_edits"]
        relocated = root / "relocated"
        shutil.copytree(repo, relocated)
        assert collect(relocated) == dirty
        tracked.unlink()
        assert collect(repo)["repositories"]["game"]["tracked_edits"]["plugin.inc"] == {"deleted": True}
        nested = repo / "not-a-repository"
        nested.mkdir()
        try:
            collect(nested)
        except subprocess.CalledProcessError as error:
            assert b"not its own Git repository" in error.output
        else:
            raise AssertionError("nested directory inherited an unrelated parent pin")
    print("provenance: immutable pin, tracked edit/delete, relocation and exact repository-root rejection passed")


if __name__ == "__main__":
    main()
