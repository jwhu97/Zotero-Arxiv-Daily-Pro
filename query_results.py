import requests

token = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI2MDMwMDI1NiIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2NDY4NzM5OCwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiIiwib3BlbklkIjpudWxsLCJ1dWlkIjoiYTQ4YzhkZGMtNjdkYS00YjcwLTgxMzItY2Q1MmQzZDhiOGJjIiwiZW1haWwiOiIiLCJleHAiOjE3NjU4OTY5OTh9.y13DAmZ8XjD_J9Do0yr-6PNlWTzQozn8POSOZ0MpYmkfRtbBXSa14V4MgVCkUTF5LZMgkqVt2o-6ZOBKpXgViw"
task_id = "0556c20e-4f2e-4657-a1e9-61922c610d35"
url = f"https://mineru.net/api/v4/extract/task/{task_id}"
header = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

res = requests.get(url, headers=header)
print(res.status_code)
print(res.json())
print(res.json()["data"])