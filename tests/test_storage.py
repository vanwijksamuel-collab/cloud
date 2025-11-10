import tempfile
import unittest
from pathlib import Path

from app import storage


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.db_path = Path(self.tmpdir.name) / "test.db"
        storage.init_db(str(self.db_path))

    def test_add_presentation_and_version(self) -> None:
        presentation = storage.ensure_presentation(
            str(self.db_path),
            logical_name="Test",
            description="Beschrijving",
            service_type="Zondag",
        )
        self.assertEqual(presentation["logical_name"], "Test")

        version = storage.add_version(
            str(self.db_path),
            presentation_id=presentation["id"],
            version_number=1,
            uploader_ip="127.0.0.1",
            uploader_name="tester",
            file_size=123,
            file_path="/tmp/file.pro7",
            original_filename="file.pro7",
            checksum="abc",
            service_type="Zondag",
            note="eerste versie",
        )

        fetched = storage.get_presentation(str(self.db_path), presentation["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["latest_version_id"], version["id"])

        versions = storage.list_versions(str(self.db_path), presentation["id"])
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["checksum"], "abc")

    def test_search_filters(self) -> None:
        presentation = storage.ensure_presentation(
            str(self.db_path),
            logical_name="Kerst",
            description="Kerstnachtdienst",
            service_type="Kerst",
        )
        storage.add_version(
            str(self.db_path),
            presentation_id=presentation["id"],
            version_number=1,
            uploader_ip=None,
            uploader_name=None,
            file_size=1,
            file_path="/tmp/x.pro7",
            original_filename="x.pro7",
            checksum="def",
            service_type="Kerst",
            note=None,
        )

        results = storage.search_presentations(str(self.db_path), search="Kerst")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["logical_name"], "Kerst")

        results_service = storage.search_presentations(str(self.db_path), service="Kerst")
        self.assertEqual(len(results_service), 1)

        results_none = storage.search_presentations(str(self.db_path), service="Jeugd")
        self.assertEqual(results_none, [])


if __name__ == "__main__":
    unittest.main()
