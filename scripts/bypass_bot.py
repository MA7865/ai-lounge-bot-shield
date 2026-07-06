"""
Known-bypass regression test.
 
This script demonstrates that a plain `requests` session - with no
JavaScript engine at all - can still get classified as "human" by
/api/courses. It never executes the /challenge page's JS and never
receives the verification cookie, but that alone only adds 2 points
("missing_human_cookie"), which is below the bot threshold of 3. As
long as the User-Agent/Accept/Accept-Language headers look like a
real browser, the score stays under the threshold.
 
Use this to verify whether a future fix (e.g. raising the weight of a
missing cookie, requiring a real JS-computed proof, or adding a
honeypot check) closes the gap: run this script before and after your
fix and compare the `status` field in the response. Before a fix,
expect "status": "human" even though no browser or JS engine was
involved and no verification cookie was ever obtained.
"""

import requests

# Base URL of your local server
BASE_URL = "http://127.0.0.1:8000"

# Step 1: Visit the challenge URL to get the verification cookie
challenge_url = f"{BASE_URL}/challenge"
session = requests.Session()

# Simulate a real browser
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# Hit challenge endpoint
challenge_resp = session.get(challenge_url, headers=headers)
print(" Challenge Page Response:", challenge_resp.text[:80], "...")

# Check cookies set
print("Cookies after challenge:", session.cookies.get_dict())

# Step 2: Call the /api/courses endpoint using same session
courses_url = f"{BASE_URL}/api/courses"
resp = session.get(courses_url, headers=headers)

print("\n API Response:")
print(resp.json())
