import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

OPTIONAL_LEGACY_PACKAGES = {
    "aiofiles",
    "aiohttp",
    "g4f",
    "keras",
    "mplfinance",
    "pandas-datareader",
    "scikit-learn",
    "scipy",
    "seaborn",
    "ta",
    "tensorboard",
    "tensorflow",
    "tensorflow-intel",
}

DEFAULT_REQUIREMENT_FILES = (
    "requirements-base.txt",
    "requirements-v1.txt",
    "requirements.txt",
    "requirements-dev.txt",
)


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def meaningful_requirement_lines(filename: str) -> list[str]:
    path = ROOT / filename
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def requirement_includes(filename: str) -> list[str]:
    includes = []
    for line in meaningful_requirement_lines(filename):
        parts = line.split()
        if parts and parts[0] in {"-r", "--requirement"} and len(parts) > 1:
            includes.append(parts[1])
    return includes


def requirement_names(filename: str) -> set[str]:
    names = set()
    for line in meaningful_requirement_lines(filename):
        if line.startswith("-"):
            continue
        requirement = line.split(";", 1)[0].strip()
        if " @ " in requirement:
            name = requirement.split(" @ ", 1)[0].strip()
        else:
            name = re.split(r"[\s<>=!~\[]", requirement, maxsplit=1)[0].strip()
        if name:
            names.add(normalize_package_name(name))
    return names


class DependencyFileTests(unittest.TestCase):
    def test_default_requirement_files_do_not_include_optional_legacy_packages(self):
        for filename in DEFAULT_REQUIREMENT_FILES:
            with self.subTest(filename=filename):
                self.assertNotIn("requirements-optional.txt", requirement_includes(filename))
                self.assertFalse(
                    requirement_names(filename) & OPTIONAL_LEGACY_PACKAGES,
                    f"{filename} should not install optional legacy dependencies by default",
                )

    def test_default_requirement_aliases_point_to_base_only(self):
        self.assertEqual(requirement_includes("requirements.txt"), ["requirements-base.txt"])
        self.assertEqual(requirement_includes("requirements-v1.txt"), ["requirements-base.txt"])

    def test_optional_requirements_are_legacy_only(self):
        self.assertEqual(requirement_includes("requirements-optional.txt"), [])
        # g4f was removed from active v1 runtime — only legacy ML/charting anchors remain.
        # matplotlib is active runtime for on-demand read-only PNG chart rendering.
        self.assertTrue(
            {"keras", "tensorflow", "mplfinance", "ta"}.issubset(
                requirement_names("requirements-optional.txt")
            )
        )
        self.assertNotIn("g4f", requirement_names("requirements-optional.txt"))
        self.assertTrue(
            requirement_names("requirements-optional.txt").issubset(OPTIONAL_LEGACY_PACKAGES)
        )

    def test_dockerfile_installs_base_dependencies_only(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8").lower()

        self.assertIn("requirements-base.txt", dockerfile)
        self.assertNotIn("requirements-optional.txt", dockerfile)
        for package in {"g4f", "keras", "tensorflow", "tensorflow-intel", "tensorboard"}:
            with self.subTest(package=package):
                self.assertNotIn(package, dockerfile)

    def test_bootstrap_does_not_install_optional_legacy_dependencies(self):
        bootstrap = (ROOT / "scripts" / "bootstrap.ps1").read_text(encoding="utf-8").lower()

        self.assertIn("requirements-v1.txt", bootstrap)
        self.assertNotIn("requirements-optional.txt", bootstrap)


if __name__ == "__main__":
    unittest.main()
