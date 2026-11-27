import random

from locust import HttpUser, TaskSet, between, task
from splent_framework.environment.host import get_host_for_locust_testing

FALLBACK_SONG_DOIS = ["10.1234/songhub-sample", "10.1234/songhub-pop"]


class SongDatasetBehavior(TaskSet):
    """Read-only browsing traffic over SongDataset pages and previews."""

    def on_start(self):
        self.song_dataset_ids = []
        self.song_file_ids = []
        self.discover_song_datasets()

    def discover_song_datasets(self):
        response = self.client.post("/explore", json={"dataset_type": "song"}, name="/explore [song]")
        if response.status_code != 200:
            return
        try:
            items = response.json()
        except ValueError:
            return
        self.song_dataset_ids = [item["id"] for item in items if item.get("id")]
        self.song_file_ids = [file["id"] for item in items for file in item.get("files", []) if file.get("id")]

    @task(5)
    def view_song_dataset(self):
        doi = random.choice(FALLBACK_SONG_DOIS)
        self.client.get(f"/doi/{doi}/", name="/doi/[song-doi]/")

    @task(4)
    def preview_song_dataset(self):
        if not self.song_dataset_ids:
            return
        dataset_id = random.choice(self.song_dataset_ids)
        self.client.get(f"/songdataset/{dataset_id}/preview?limit=25&offset=0", name="/songdataset/[id]/preview")

    @task(2)
    def explore_song_artist(self):
        self.client.post("/explore", json={"query": "Gorillaz", "dataset_type": "song"}, name="/explore [Gorillaz]")

    @task(1)
    def download_song_csv(self):
        if not self.song_file_ids:
            return
        file_id = random.choice(self.song_file_ids)
        self.client.get(f"/songdataset/file/{file_id}/download", name="/songdataset/file/[id]/download")


class SongDatasetUser(HttpUser):
    tasks = [SongDatasetBehavior]
    wait_time = between(1, 3)
    host = get_host_for_locust_testing()
