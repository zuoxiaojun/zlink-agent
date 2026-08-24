"""Build utilities — cross-platform helpers for build scripts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def is_windows() -> bool:
    """Detect if running under Windows (MSYS2/Git Bash/Cygwin or native Windows)."""
    return sys.platform.startswith("win") or os.name == "nt"


def python_bin_path(bundle_dir: str) -> str:
    """Return the Python executable path inside a venv bundle dir.

    Unix:    <bundle_dir>/bin/python
    Windows: <bundle_dir>/Scripts/python.exe
    """
    if is_windows():
        return os.path.join(bundle_dir, "Scripts", "python.exe")
    return os.path.join(bundle_dir, "bin", "python")


def clean_pycache(root_dir: str) -> None:
    """Remove __pycache__ dirs and .pyc files recursively (cross-platform)."""
    root = Path(root_dir)
    for item in root.rglob("__pycache__"):
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
    for item in root.rglob("*.pyc"):
        if item.is_file():
            item.unlink(missing_ok=True)


def remove_test_dirs(root_dir: str) -> None:
    """Remove Python 'test' directories under lib/ (cross-platform)."""
    root = Path(root_dir)
    lib_python = root / "lib"
    if lib_python.is_dir():
        for py_ver_dir in lib_python.iterdir():
            test_dir = py_ver_dir / "test"
            if test_dir.is_dir():
                shutil.rmtree(test_dir, ignore_errors=True)
            # also clean site-packages tests
            for pat in ("tests", "testing", "test_"):
                for d in py_ver_dir.rglob(pat):
                    if d.is_dir() and d.parent.name == "site-packages":
                        shutil.rmtree(d, ignore_errors=True)


def dir_size_mb(root_dir: str) -> str:
    """Return human-readable directory size in MB (cross-platform)."""
    total = 0
    root = Path(root_dir)
    for item in root.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return f"{total / (1024 * 1024):.1f} MB"


def remove_paths(*paths: str) -> None:
    """Remove files or directories (cross-platform)."""
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def relocate_python_bundle(bundle_dir: str) -> None:
    """Make the macOS Python bundle self-contained and relocatable.

    Problem: ``python3.14`` in the venv is an absolute symlink to
    Homebrew's Python framework (e.g. ``/opt/homebrew/.../python3.14``),
    which breaks on other machines.  The venv also lacks the stdlib
    (``os.py``, ``json/``, ``lib-dynload/``, etc.) — those live inside
    Homebrew's ``Python.framework``.

    macOS Framework Python has a multi-component layout:
      bin/python3.14              → stub that exec's MacOS/Python
      Resources/Python.app/.../MacOS/Python  → the real interpreter binary
      Python                      → framework dylib

    This function:
      1. Replaces the ``python3.14`` symlink with a copy of the real
         interpreter binary (``MacOS/Python``)
      2. Copies the Python framework dylib (``Python``) into ``lib/``
      3. Fixes dylib load paths with ``install_name_tool``
      4. Re-signs both binaries with ad-hoc signature
      5. Copies the full stdlib from Homebrew
      6. Copies and relocates any Homebrew dylibs referenced by .so files
         (libmpdec, libcrypto, libssl, libzstd, liblzma, libsqlite3, etc.)
    """
    if is_windows():
        return
    bundle = Path(bundle_dir).resolve()
    if not bundle.is_dir():
        return

    venv_python = bundle / "bin" / "python3.14"
    if not venv_python.is_symlink():
        print("  ℹ️  python3.14 is not a symlink, already relocatable")
        return

    real_python = os.path.realpath(venv_python)
    print(f"  🔗  python3.14 symlink -> {real_python}")
    # real_python is: .../Python.framework/Versions/3.14/bin/python3.14 (the stub)
    ver_dir = Path(real_python).resolve().parent.parent  # .../Versions/3.14/

    framework_dylib = ver_dir / "Python"
    # The real interpreter is at Resources/Python.app/Contents/MacOS/Python
    real_interp = ver_dir / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"
    stdlib_src = ver_dir / "lib" / "python3.14"

    if not framework_dylib.is_file():
        print(f"  ⚠️  Framework dylib not found at {framework_dylib}, skipping")
        return
    if not real_interp.is_file():
        print(f"  ⚠️  Real interpreter not found at {real_interp}, skipping")
        return
    if not stdlib_src.is_dir():
        print(f"  ⚠️  Stdlib not found at {stdlib_src}, skipping")
        return

    # ── Step 1: replace symlink with REAL interpreter binary ──
    venv_python.unlink()
    shutil.copy2(real_interp, venv_python)
    os.chmod(venv_python, 0o755)
    print("  ✅  Replaced python3.14 symlink with real interpreter binary")

    # Also recreate python and python3 symlinks to python3.14
    for link_name in ("python", "python3"):
        link_path = bundle / "bin" / link_name
        if link_path.is_symlink() and not link_path.exists():
            link_path.unlink()
            os.symlink("python3.14", link_path)
            print(f"  ✅  Recreated broken symlink bin/{link_name} -> python3.14")

    # ── Step 2: copy framework dylib into lib/ ──
    lib_dir = bundle / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    dylib_dst = lib_dir / "libpython3.14.dylib"
    shutil.copy2(framework_dylib, dylib_dst)
    os.chmod(dylib_dst, 0o755)
    print(f"  ✅  Copied framework dylib -> {dylib_dst}")

    # ── Step 3: fix dylib load paths ──
    dylib_rpath = "@executable_path/../lib/libpython3.14.dylib"

    otool_out = subprocess.check_output(["otool", "-L", str(venv_python)], text=True)
    old_dylib_paths = []
    for line in otool_out.splitlines():
        line = line.strip()
        if "Python.framework" in line and "Python" in line:
            old_path = line.split()[0]
            old_dylib_paths.append(old_path)

    for old in old_dylib_paths:
        subprocess.run(
            ["install_name_tool", "-change", old, dylib_rpath, str(venv_python)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"  ✅  Fixed interpreter: {old} -> {dylib_rpath}")

    # Fix the dylib's own install name
    subprocess.run(
        ["install_name_tool", "-id", dylib_rpath, str(dylib_dst)],
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"  ✅  Fixed dylib install name -> {dylib_rpath}")

    # ── Step 4: ad-hoc re-sign ──
    subprocess.run(
        ["codesign", "--force", "--sign", "-", str(venv_python)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["codesign", "--force", "--sign", "-", str(dylib_dst)],
        check=True,
        capture_output=True,
        text=True,
    )
    print("  ✅  Ad-hoc re-signed binaries")

    # ── Step 5: copy stdlib (merge, don't destroy site-packages) ──
    stdlib_dst = bundle / "lib" / "python3.14"

    subprocess.run(
        [
            "rsync",
            "-a",
            "--exclude=__pycache__",
            "--exclude=*.pyc",
            "--exclude=/site-packages",  # preserve venv's site-packages
            f"{stdlib_src}/",
            f"{stdlib_dst}/",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"  ✅  Copied stdlib ({dir_size_mb(str(stdlib_dst))})")

    # Fix broken config-* symlinks that pointed into the framework
    for config_dir in stdlib_dst.glob("config-*-darwin"):
        if config_dir.is_dir():
            for link_name in ("libpython3.14.a", "libpython3.14.dylib"):
                link_path = config_dir / link_name
                if link_path.is_symlink() and not link_path.exists():
                    link_path.unlink()
                    # Relink to libpython3.14.dylib in the parent lib/ dir
                    os.symlink("../../libpython3.14.dylib", link_path)
                    print(f"  ✅  Fixed config symlink: {config_dir.name}/{link_name}")

    # ── Step 6: relocate Homebrew dylibs referenced by .so files ──
    _relocate_homebrew_dylibs(bundle)

    # ── Step 6.5: fix Rust .so @rpath self-references ──
    # Rust-compiled native extensions (e.g. pydantic_core, cryptography)
    # set their own install name to @rpath/xxx.so, which works on the
    # build machine (Homebrew Python Framework registers @rpath) but
    # fails on user machines.  Fix by replacing @rpath/ with @loader_path/.
    _fix_rpath_self_references(bundle)

    # ── Step 7: verify ──
    for mod_name in ("sys", "pydantic", "pydantic_core", "cryptography"):
        result = subprocess.run(
            [str(venv_python), "-c", f"import {mod_name}"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(bundle),
        )
        if result.returncode == 0:
            print(f"  ✅  import {mod_name}")
        else:
            print(f"  ⚠️  import {mod_name} FAILED:\n{result.stderr[:300]}")


def _relocate_homebrew_dylibs(bundle: Path) -> None:
    """Find and bundle Homebrew dylibs referenced by .so files.

    Scans all ``.so`` files in the bundle for references to
    ``/opt/homebrew/opt/...``, copies the actual dylib files into
    ``lib/``, and rewrites both the reference in the caller and the
    dylib's own install name to use ``@rpath``.
    """
    lib_dir = bundle / "lib"
    so_files = list(bundle.rglob("*.so"))
    if not so_files:
        return

    # Collect unique (old_path, resolved_real) pairs
    deps: dict[str, str] = {}  # old_path -> resolved real path
    for so in so_files:
        try:
            out = subprocess.check_output(["otool", "-L", str(so)], text=True).splitlines()
        except subprocess.CalledProcessError:
            continue
        for line in out:
            line = line.strip()
            if "/opt/homebrew/" in line:
                old_path = line.split()[0]
                resolved = os.path.realpath(old_path)
                deps[old_path] = resolved

    if not deps:
        return

    print(f"  📦  Found {len(deps)} Homebrew dylib reference(s), bundling...")

    # Iteratively resolve transitive dependencies: bundle dylibs, scan them
    # for remaining Homebrew refs, and repeat until clean.
    name_map: dict[str, str] = {}  # old_path -> dylib filename
    bundled_real: set[str] = set()  # real paths already copied

    for old_path in deps:
        name_map[old_path] = os.path.basename(old_path)

    queue = list(deps.values())  # real paths to process
    while queue:
        real_path = queue.pop()

        # If we haven't bundled this real path yet, do it
        if real_path not in bundled_real:
            dylib_name = os.path.basename(real_path)
            local_path = lib_dir / dylib_name
            if not local_path.is_file():
                shutil.copy2(real_path, local_path)
                os.chmod(local_path, 0o755)
                subprocess.run(
                    ["install_name_tool", "-id", f"@executable_path/../lib/{dylib_name}", str(local_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            bundled_real.add(real_path)

        # Scan for transitive deps (even if already bundled, to catch
        # different symlink aliases — e.g. openssl@3/lib vs Cellar path)
        local_path = lib_dir / os.path.basename(real_path)
        if not local_path.is_file():
            continue
        try:
            out = subprocess.check_output(["otool", "-L", str(local_path)], text=True).splitlines()
        except subprocess.CalledProcessError:
            continue
        for line in out:
            line = line.strip()
            if "/opt/homebrew/" in line and "Python.framework" not in line:
                trans_path = line.split()[0]
                if trans_path not in name_map:
                    name_map[trans_path] = os.path.basename(trans_path)
                    trans_real = os.path.realpath(trans_path)
                    if trans_real not in bundled_real:
                        queue.append(trans_real)

    # Now rewrite all references in all binaries
    all_binaries: list[Path] = list(so_files) + [
        lib_dir / "libpython3.14.dylib",
        bundle / "bin" / "python3.14",
    ]
    for dylib in lib_dir.glob("lib*.dylib"):
        if dylib not in all_binaries:
            all_binaries.append(dylib)

    for binary in all_binaries:
        if not binary.is_file():
            continue
        for old_path, dylib_name in name_map.items():
            new_path = f"@executable_path/../lib/{dylib_name}"
            try:
                subprocess.run(
                    ["install_name_tool", "-change", old_path, new_path, str(binary)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError:
                pass  # reference not in this binary

    # Ad-hoc re-sign all bundled dylibs
    for f in lib_dir.glob("lib*.dylib"):
        if f.is_file():
            subprocess.run(
                ["codesign", "--force", "--sign", "-", str(f)],
                check=False,
                capture_output=True,
                text=True,
            )

    # Create symlink aliases when the old_path basename differs from the
    # versioned real filename (e.g. libzstd.1.dylib → libzstd.1.5.7.dylib)
    fixed_symlinks = 0
    for old_path, ref_name in name_map.items():
        real_name = os.path.basename(os.path.realpath(old_path))
        if real_name != ref_name:
            local_symlink = lib_dir / ref_name
            if not local_symlink.exists():
                os.symlink(real_name, local_symlink)
                fixed_symlinks += 1
    if fixed_symlinks:
        print(f"  ✅  Created {fixed_symlinks} dylib symlink alias(es) (version → unversioned)")

    print(f"  ✅  Bundled and relocated {len(deps)} Homebrew dylib(s)")


def _fix_rpath_self_references(bundle: Path) -> None:
    """Fix Rust .so files whose own install name is @rpath/xxx.so.

    These files set their own install name to @rpath/<filename>, relying on
    the Python interpreter's ``-Wl,-rpath`` to resolve it.  On the build
    machine (Homebrew Python Framework) this works; on user machines without
    Homebrew it fails at import time.

    Fix: change the install name from ``@rpath/<filename>`` to
    ``@loader_path/<filename>`` so it resolves relative to the .so itself.
    """
    so_files = list(bundle.rglob("*.so"))
    fixed = 0
    for so in so_files:
        try:
            out = subprocess.check_output(["otool", "-L", str(so)], text=True).splitlines()
        except subprocess.CalledProcessError:
            continue
        # First line is the file's own install name
        own_name = out[0].strip() if out else ""
        if own_name.startswith("@rpath/"):
            loader_path = "@loader_path/" + Path(own_name).name
            try:
                subprocess.run(
                    ["install_name_tool", "-id", loader_path, str(so)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                print(f"  ✅  Fixed @rpath self-ref: {so.relative_to(bundle)} -> {loader_path}")
                fixed += 1
            except subprocess.CalledProcessError:
                print(f"  ⚠️  Failed to fix @rpath for {so.relative_to(bundle)}")
        # Also fix any other @rpath references in the same file
        for line in out[1:]:
            line = line.strip()
            if line.startswith("@rpath/"):
                old = line.split()[0]
                new = "@loader_path/" + Path(old).name
                try:
                    subprocess.run(
                        ["install_name_tool", "-change", old, new, str(so)],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    print(f"  ✅  Fixed @rpath dep: {so.relative_to(bundle)}: {old} -> {new}")
                    fixed += 1
                except subprocess.CalledProcessError:
                    pass

    # Also scan .dylib files in lib/ for @rpath references
    for dylib in (bundle / "lib").glob("*.dylib"):
        try:
            out = subprocess.check_output(["otool", "-L", str(dylib)], text=True).splitlines()
        except subprocess.CalledProcessError:
            continue
        for line in out[1:]:
            line = line.strip()
            if line.startswith("@rpath/"):
                old = line.split()[0]
                new = "@loader_path/" + Path(old).name
                try:
                    subprocess.run(
                        ["install_name_tool", "-change", old, new, str(dylib)],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    print(f"  ✅  Fixed @rpath dylib: {dylib.relative_to(bundle)}: {old} -> {new}")
                    fixed += 1
                except subprocess.CalledProcessError:
                    pass

    if fixed:
        print(f"  ✅  Fixed {fixed} @rpath reference(s) in native extensions")
        # Re-sign after changes
        for so in so_files:
            subprocess.run(["codesign", "--force", "--sign", "-", str(so)], check=False, capture_output=True, text=True)
        for dylib in (bundle / "lib").glob("*.dylib"):
            subprocess.run(
                ["codesign", "--force", "--sign", "-", str(dylib)], check=False, capture_output=True, text=True
            )
