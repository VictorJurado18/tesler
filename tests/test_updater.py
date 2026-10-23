from dragshift import __version__, updater


def test_versions():
    assert updater.parse_version("v2.10.1") == (2, 10, 1)
    assert updater.parse_version("2.1") == (2, 1, 0)
    assert updater.is_newer("2.0.1", "2.0.0") and updater.is_newer("2.10.0", "2.9.9")
    assert not updater.is_newer("2.0.0", "2.0.0") and not updater.is_newer("1.9.0", "2.0.0")


def test_release_json():
    data = {"tag_name": "v2.1.0", "body": "- novo\n\n---\nbuild", "html_url": "https://x",
            "assets": [{"name": "Tesler-Setup.exe", "browser_download_url": "https://x/s.exe", "size": 10,
                        "digest": "sha256:ABC"}, {"name": "Tesler-Portable.exe"}]}
    r = updater.release_from_json(data)
    assert (r.version, r.setup_url, r.setup_size, r.sha256) == ("2.1.0", "https://x/s.exe", 10, "abc")
    assert updater.tidy_notes(r.notes) == "- novo"
    assert updater.release_from_json({"tag_name": "latest"}) is None
    assert updater.release_from_json({"tag_name": "v3.0.0", "prerelease": True}) is None


def test_changelog_has_current_version():
    md = "# x\n## 2.1.0\n- a\n## 2.0.0\n- b\n"
    assert updater.notes_for("2.1.0", md) == "- a"
    assert updater.notes_for("2.0.0", md) == "- b"
    assert updater.notes_for(__version__)   # every version bump needs its CHANGELOG section
