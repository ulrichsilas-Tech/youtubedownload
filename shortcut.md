# iOS Shortcut: "Download from yt-dlp API"

## Setup
1. Deploy this API to Render (see below)
2. Note your Render URL: `https://yt-dlp-api.onrender.com`
3. Create this shortcut on iPhone:

## Shortcut Steps
```
1. Ask for Input → "YouTube URL" (Type: URL)
2. Get Contents of URL
   - URL: https://youtubedownload-ftpc.onrender.com/download
   - Method: POST
   - Request Body: JSON
     {
       "url": "Provided Input",
       "format": "mp3",
       "quality": "192"
     }
   - Headers: Content-Type: application/json
   - Show More → Get: Response Body
3. Get Dictionary Value → Key: "download_url"
4. Get Contents of URL
   - URL: https://youtubedownload-ftpc.onrender.com + download_url
   - Method: GET
5. Save File
   - Ask Where to Save: On
   - Default Location: Documents (iCloud Drive)
```

## Import via iCloud
Share this shortcut via iCloud link or recreate manually in Shortcuts app.

## Render Deploy Steps
1. Push this folder to GitHub
2. Connect repo to Render
3. Render auto-detects `render.yaml` → deploys
4. First deploy takes 3-5 min (installs ffmpeg, yt-dlp)
5. Free tier sleeps after 15min inactivity → first request takes ~30s to wake

## Notes
- Files auto-deleted after download (cleanup task)
- Max file size limited by Render disk (1GB) and memory (512MB)
- For large videos (>100MB), consider format=mp4 with lower quality