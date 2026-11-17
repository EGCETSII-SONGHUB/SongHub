from locust import HttpUser, TaskSet, between, task
from splent_framework.environment.host import get_host_for_locust_testing


class CommunityBehavior(TaskSet):
    @task
    def index(self):
        response = self.client.get("/community")
        if response.status_code != 200:
            print(f"Community index failed: {response.status_code}")


class CommunityUser(HttpUser):
    tasks = [CommunityBehavior]
    wait_time = between(5, 9)
    host = get_host_for_locust_testing()
