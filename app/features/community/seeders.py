import os
import shutil

from dotenv import load_dotenv
from splent_framework.configuration.configuration import uploads_folder_name
from splent_framework.seeders.BaseSeeder import BaseSeeder

from app.features.auth.models import User
from app.features.community.models import Community
from app.features.dataset.models import DataSet


class CommunitySeeder(BaseSeeder):
    """Seed initial communities, curators, logos, and dataset links."""

    priority = 3  # Runs after AuthSeeder (1) and DataSetSeeder (2)

    def run(self):
        user1 = User.query.filter_by(email="user1@example.com").first()
        user2 = User.query.filter_by(email="user2@example.com").first()

        if not user1 or not user2:
            raise Exception("Users not found. Please seed users first.")

        load_dotenv()
        working_dir = os.getenv("WORKING_DIR", "")
        static_logos_dir = os.path.join(working_dir, "app", "static", "img", "logos")
        dest_logos_dir = os.path.join(working_dir, uploads_folder_name(), "communities")
        os.makedirs(dest_logos_dir, exist_ok=True)

        seville_logo = self._copy_sample_logo(static_logos_dir, dest_logos_dir, "university_of_seville.svg")
        malaga_logo = self._copy_sample_logo(static_logos_dir, dest_logos_dir, "university_of_malaga.svg")

        communities = [
            Community(
                name="University of Seville",
                description="Official community for research datasets curated at the University of Seville.",
                logo=seville_logo,
                creator_id=user1.id,
            ),
            Community(
                name="DiversoLab Research",
                description="Open science datasets and collections maintained by DiversoLab.",
                logo=malaga_logo,
                creator_id=user2.id,
            ),
        ]
        seeded_communities = self.seed(communities)

        us_community, diverso_community = seeded_communities
        us_community.curators.append(user1)
        diverso_community.curators.append(user2)
        diverso_community.curators.append(user1)

        user1_datasets = DataSet.query.filter_by(user_id=user1.id).all()
        user2_datasets = DataSet.query.filter_by(user_id=user2.id).all()

        for dataset in user1_datasets:
            us_community.datasets.append(dataset)
        for dataset in user2_datasets:
            diverso_community.datasets.append(dataset)

        self.db.session.commit()

    @staticmethod
    def _copy_sample_logo(src_dir: str, dest_dir: str, filename: str) -> str | None:
        src_path = os.path.join(src_dir, filename)
        if not os.path.isfile(src_path):
            return None
        dest_path = os.path.join(dest_dir, filename)
        shutil.copy(src_path, dest_path)
        return filename
