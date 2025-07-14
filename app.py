from flask import Flask, render_template, request, redirect, url_for, Response
import requests
from utils.innertube import innertube_search, innertube_trending, innertube_browse, innertube_comments
from utils.streamer import GetVideo, extract_video_id

app = Flask(__name__)
streamer = GetVideo()

@app.route("/")
def index():
    videos = innertube_trending(trending_type=None, region="US", max_results=20)
    return render_template("index.html", videos=videos)

@app.errorhandler(404)
@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_error(e):
    status_code = getattr(e, 'code', 500)
    message = str(e) if status_code != 404 else "Page not found"
    return render_template("error.html", message=message), status_code


@app.route("/search")
def search():
    q = request.args.get("q", "")
    if not q:
        return redirect(url_for("index"))
    videos = innertube_search(q, region="US", max_results=30)
    return render_template("search.html", videos=videos, query=q)

@app.route("/watch")
def watch():
    video_id = request.args.get("v")
    if not video_id:
        return redirect(url_for("index"))

    data = streamer.fetch_video_data(video_id)
    details = data.get("videoDetails", {})
    streaming_data = data.get("streamingData", {})
    formats = streaming_data.get("adaptiveFormats", []) + streaming_data.get("formats", [])
    stream, size = streamer.get_stream_url(formats, preference="highest")

    if not stream:
        playability = data.get("playabilityStatus", {})
        reason = playability.get("reason")
        subreason = ""
        if "errorScreen" in playability:
            runs = playability["errorScreen"].get("playerErrorMessageRenderer", {}).get("subreason", {}).get("runs", [])
            subreason = " ".join([r.get("text", "") for r in runs])

        message = reason or "No stream found"
        if subreason:
            message += f": {subreason}"

        return render_template("error.html", message=message), 403

    sort_by = request.args.get("sort_by", "top")
    max_results = int(request.args.get("max_comments", 20))
    try:
        comments_data = innertube_comments(video_id, max_results=max_results, sort_by=sort_by)
    except Exception as e:
        print(f"comment error: {str(e)}")
        comments_data = []

    comments = []
    for comment in comments_data:
        replies = comment.get("replies", [])[:5]
        comments.append({
            "author": comment.get("author", ""),
            "text": comment.get("text", ""),
            "replies": replies
        })

    return render_template(
        "video.html",
        video=details,
        stream_url=url_for("proxy_stream", video_url=stream["url"]),
        comments=comments,
        sort_by=sort_by,
        max_results=max_results
    )

@app.route("/stream")
def proxy_stream():
    video_url = request.args.get("video_url")
    if not video_url:
        return "Missing url", 400

    upstream = requests.get(video_url, stream=True)
    if upstream.status_code != 200:
        return upstream.text, upstream.status_code

    def generate():
        for chunk in upstream.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    return Response(
        generate(),
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "video/mp4"),
    )

@app.route("/thumbnail/<video_id>")
def proxy_thumbnail(video_id):
    thumb_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    response = requests.get(thumb_url, stream=True)
    if response.status_code != 200:
        return "Thumbnail fetch failed", response.status_code

    def generate():
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    return Response(
        generate(),
        status=response.status_code,
        content_type=response.headers.get("Content-Type", "image/jpeg"),
    )

@app.route("/channel/<channel_id>")
def channel(channel_id):
    data = innertube_browse(channel_id)
    channel_info = {
        "title": data.get("metadata", {}).get("title", "Unknown Channel"),
        "description": data.get("metadata", {}).get("description", ""),
        "subscriberCount": data.get("metadata", {}).get("subscriberCountText", "No subscribers"),
        "thumbnails": data.get("metadata", {}).get("thumbnails", []),
        "videos": data.get("videos", [])
    }
    
    return render_template("channel.html", channel=channel_info)

@app.route("/ggpht/<path:url_path>")
def proxy_ggpht(url_path):
    base_url = "https://yt3.googleusercontent.com"
    full_url = f"{base_url}/{url_path}"
    
    try:
        response = requests.get(full_url, stream=True)
        if response.status_code != 200:
            return "Image fetch failed", response.status_code

        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        return Response(
            generate(),
            content_type=response.headers.get("Content-Type", "image/jpeg"),
            headers={
                "Cache-Control": "public, max-age=86400"
            }
        )
    except Exception as e:
        print(f"Error proxying ggpht image: {str(e)}")
        return "Image proxy error", 500

@app.route("/embed/<video_id>")
def embed(video_id):
    if not video_id:
        return "No video ID provided", 400

    data = streamer.fetch_video_data(video_id)
    details = data.get("videoDetails", {})
    streaming_data = data.get("streamingData", {})
    formats = streaming_data.get("adaptiveFormats", []) + streaming_data.get("formats", [])
    stream, _ = streamer.get_stream_url(formats, preference="highest")

    if not stream:
        return "No stream found", 404

    return render_template(
        "embed.html",
        video=details,
        stream_url=url_for("proxy_stream", video_url=stream["url"])
    )

if __name__ == "__main__":
    app.run(debug=True, port=3044)
