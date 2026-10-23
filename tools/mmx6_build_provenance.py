"""Local declared-build provenance: immutable Git pins, tracked edits, cache."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--repository", action="append", default=[])
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    roots = []
    for value in args.root:
        label, path = value.split("=", 1)
        if path:
            roots.append((label, Path(path).resolve()))
    roots.sort(key=lambda item: len(str(item[1])), reverse=True)

    def normalize(text):
        for label, path in roots:
            for spelling in {str(path), path.as_posix()}:
                text = re.sub(re.escape(spelling) + r"(?=$|[/\\;\s\"',>])",
                              lambda match: "${" + label + "}", text)
        return text

    repositories = {}
    for value in args.repository:
        label, raw = value.split("=", 1)
        root = Path(raw).resolve()
        top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        if top != root:
            raise ValueError("dependency directory is not its own Git repository: " + label)
        head = git(root, "rev-parse", "--verify", "HEAD").decode().strip()
        if not re.fullmatch(r"[0-9a-f]{40,64}", head):
            raise ValueError("repository has no immutable Git identity: " + label)
        changed = git(root, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", "HEAD", "--").split(b"\0")
        edits = {}
        for raw_name in changed:
            if not raw_name:
                continue
            name = raw_name.decode("utf-8")
            path = root / name
            if path.is_file():
                before = path.stat()
                data = path.read_bytes()
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("tracked input changed during hashing: " + name)
                edits[name] = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            elif not path.exists():
                edits[name] = dict(deleted=True)
            else:
                edits[name] = dict(gitlink=git(path, "rev-parse", "HEAD").decode().strip())
        raw_status = git(root, "diff", "--no-ext-diff", "--no-textconv", "--raw", "-z", "HEAD", "--")
        repositories[label] = dict(head=head, tracked_edits=edits,
                                  tracked_status_sha256=hashlib.sha256(raw_status).hexdigest())
    cache = {}
    for line in args.cache.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "//")) and "=" in line:
            key, value = line.split("=", 1)
            cache[normalize(key)] = normalize(value)
    data = dict(schema=1, scope="declared-repositories-and-cache-v1",
                repositories=repositories, cmake_cache=cache,
                limitations=["untracked dependency implementation files are not Git pins",
                             "compiler sysroot and external binary provenance are not exhaustive"])
    encoded = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists() or args.output.read_bytes() != encoded:
        args.output.write_bytes(encoded)


if __name__ == "__main__":
    main()
