import httpx
import sys

def test_health():
    try:
        resp = httpx.get("http://localhost:8000/health")
        print(f"/health status: {resp.status_code}, body: {resp.json()}")
        assert resp.status_code == 200
    except Exception as e:
        print(f"/health failed: {e}")
        sys.exit(1)

def test_login():
    try:
        resp = httpx.get("http://localhost:8000/auth/login", follow_redirects=False)
        print(f"/auth/login status: {resp.status_code}, Location: {resp.headers.get('location')}")
        assert resp.status_code in [302, 307]
        assert "login.microsoftonline.com/common" in resp.headers.get("location")
    except Exception as e:
        print(f"/auth/login failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_health()
    test_login()
    print("All checks passed successfully!")
