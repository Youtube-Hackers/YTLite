import re
import requests

def fetch_watch_html(video_url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    r = requests.get(video_url, headers=headers)
    r.raise_for_status()
    return r.text

def extract_innertube_with_regex(html: str) -> dict:
    data = {}
    patterns = {
        "api_key": r'["\']INNERTUBE_API_KEY["\']\s*:\s*["\']([^"\']+)["\']',
        "client_version": r'["\']INNERTUBE_CONTEXT_CLIENT_VERSION["\']\s*:\s*["\']([^"\']+)["\']',
        "visitor_data": r'["\']VISITOR_DATA["\']\s*:\s*["\']([^"\']+)["\']',
    }

    for key, pat in patterns.items():
        m = re.search(pat, html)
        data[key] = m.group(1) if m else None

    return data

def main():
    watch_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print("Downloading from YouTube...")
    html = fetch_watch_html(watch_url)

    print("Extracting Infos...")
    params = extract_innertube_with_regex(html)

    print("\nInfos:")
    for k, v in params.items():
        print(f"{k:15}: {v}")

if __name__ == "__main__":
    main()
