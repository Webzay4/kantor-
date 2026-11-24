import os
import asyncio
import httpx


async def publish_to_youtube(cfg: dict, filepath: str, title: str, script: str) -> dict:
    client_id = cfg.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = cfg.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = cfg.get("YOUTUBE_REFRESH_TOKEN", "").strip()
    privacy = cfg.get("YOUTUBE_PRIVACY_STATUS", "public").strip() or "public"

    if not (client_id and client_secret and refresh_token):
        return {"ok": False, "status": "skipped", "message": "Kredensial YouTube belum diisi."}

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            token_res.raise_for_status()
            access_token = token_res.json()["access_token"]

            with open(filepath, "rb") as f:
                video_bytes = f.read()
            file_size = len(video_bytes)

            metadata = {
                "snippet": {
                    "title": f"{title[:85]} #Shorts",
                    "description": f"{script}\n\n#Shorts #AI #Animasi",
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": False,
                },
            }
            init_res = await client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Length": str(file_size),
                    "X-Upload-Content-Type": "video/mp4",
                },
                json=metadata,
            )
            init_res.raise_for_status()
            upload_url = init_res.headers.get("Location") or init_res.headers.get("location")

            up_res = await client.put(
                upload_url,
                headers={"Content-Type": "video/mp4", "Content-Length": str(file_size)},
                content=video_bytes,
            )
            up_res.raise_for_status()
            video_id = up_res.json().get("id")
            return {
                "ok": True,
                "status": "published",
                "url": f"https://youtube.com/shorts/{video_id}",
                "message": f"Tayang di YouTube Shorts (ID: {video_id})",
            }
    except Exception as e:
        return {"ok": False, "status": "error", "message": f"YouTube error: {e}"}


async def publish_to_instagram(cfg: dict, filepath: str, media_url: str, title: str, script: str) -> dict:
    ig_user_id = cfg.get("IG_USER_ID", "").strip()
    access_token = cfg.get("IG_ACCESS_TOKEN", "").strip()
    graph_host = cfg.get("IG_GRAPH_HOST", "graph.facebook.com").strip() or "graph.facebook.com"
    public_base = cfg.get("PUBLIC_BASE_URL", "").strip().rstrip("/")

    if not (ig_user_id and access_token):
        return {"ok": False, "status": "skipped", "message": "Kredensial Instagram belum diisi."}

    caption = f"{title}\n\n{script}\n\n#Reels #AnimasiAI #KontenOtomatis"

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            if public_base and public_base.startswith("https://"):
                c_res = await client.post(
                    f"https://{graph_host}/v24.0/{ig_user_id}/media",
                    params={
                        "media_type": "REELS",
                        "video_url": f"{public_base}{media_url}",
                        "caption": caption,
                        "share_to_feed": "true",
                        "access_token": access_token,
                    },
                )
                c_res.raise_for_status()
                container_id = c_res.json()["id"]
            else:
                c_res = await client.post(
                    f"https://graph.facebook.com/v24.0/{ig_user_id}/media",
                    params={
                        "media_type": "REELS",
                        "upload_type": "resumable",
                        "caption": caption,
                        "share_to_feed": "true",
                        "access_token": access_token,
                    },
                )
                c_res.raise_for_status()
                c_data = c_res.json()
                container_id = c_data["id"]
                rupload_uri = c_data.get("uri") or f"https://rupload.facebook.com/ig-api-upload/v24.0/{container_id}"

                with open(filepath, "rb") as f:
                    video_bytes = f.read()

                up_res = await client.post(
                    rupload_uri,
                    headers={
                        "Authorization": f"OAuth {access_token}",
                        "offset": "0",
                        "file_size": str(len(video_bytes)),
                    },
                    content=video_bytes,
                )
                up_res.raise_for_status()

            for _ in range(30):
                await asyncio.sleep(4)
                st_res = await client.get(
                    f"https://{graph_host}/v24.0/{container_id}",
                    params={"fields": "status_code,status", "access_token": access_token},
                )
                st_res.raise_for_status()
                st_data = st_res.json()
                code = st_data.get("status_code")
                if code == "FINISHED":
                    break
                if code in ("ERROR", "EXPIRED"):
                    raise RuntimeError(f"Container IG gagal: {st_data}")

            pub_res = await client.post(
                f"https://{graph_host}/v24.0/{ig_user_id}/media_publish",
                params={"creation_id": container_id, "access_token": access_token},
            )
            pub_res.raise_for_status()
            ig_media_id = pub_res.json().get("id")
            return {
                "ok": True,
                "status": "published",
                "message": f"Tayang di Instagram Reels (Media ID: {ig_media_id})",
            }
    except Exception as e:
        return {"ok": False, "status": "error", "message": f"Instagram error: {e}"}


async def get_tiktok_access_token(cfg: dict, client: httpx.AsyncClient) -> str:
    direct_token = cfg.get("TIKTOK_ACCESS_TOKEN", "").strip()
    client_key = cfg.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = cfg.get("TIKTOK_CLIENT_SECRET", "").strip()
    refresh_token = cfg.get("TIKTOK_REFRESH_TOKEN", "").strip()

    if client_key and client_secret and refresh_token:
        res = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        if res.status_code == 200 and "access_token" in res.json():
            return res.json()["access_token"]
    return direct_token


async def publish_to_tiktok(cfg: dict, filepath: str, title: str, script: str) -> dict:
    post_mode = (cfg.get("TIKTOK_POST_MODE", "draft").strip() or "draft").lower()
    privacy_level = cfg.get("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY").strip() or "SELF_ONLY"

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            access_token = await get_tiktok_access_token(cfg, client)
            if not access_token:
                return {"ok": False, "status": "skipped", "message": "Token TikTok belum diisi."}

            with open(filepath, "rb") as f:
                video_bytes = f.read()
            file_size = len(video_bytes)

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            }

            if post_mode == "direct":
                init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
                payload = {
                    "post_info": {
                        "title": f"{title} — {script[:80]} #AI #Animasi",
                        "privacy_level": privacy_level,
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": file_size,
                        "chunk_size": file_size,
                        "total_chunk_count": 1,
                    },
                }
            else:
                init_url = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
                payload = {
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": file_size,
                        "chunk_size": file_size,
                        "total_chunk_count": 1,
                    }
                }

            init_res = await client.post(init_url, headers=headers, json=payload)
            init_res.raise_for_status()
            init_data = init_res.json()
            if init_data.get("error", {}).get("code") not in (None, "ok"):
                raise RuntimeError(init_data["error"])

            upload_url = init_data["data"]["upload_url"]
            publish_id = init_data["data"]["publish_id"]

            put_res = await client.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                    "Content-Type": "video/mp4",
                },
                content=video_bytes,
            )
            put_res.raise_for_status()

            label = "Draft/Inbox TikTok" if post_mode != "direct" else f"Profil TikTok ({privacy_level})"
            return {
                "ok": True,
                "status": "published",
                "message": f"Terkirim ke {label} (Publish ID: {publish_id})",
            }
    except Exception as e:
        return {"ok": False, "status": "error", "message": f"TikTok error: {e}"}


async def publish_to_platforms(cfg: dict, platforms: list[str], filepath: str, media_url: str, media_type: str, title: str, script: str) -> dict:
    results = {}

    if media_type != "mp4":
        for p in platforms:
            results[p] = {
                "ok": False,
                "status": "demo_only",
                "message": "Mode Demo (.gif) tidak bisa diupload ke Sosmed. Isi REPLICATE_API_TOKEN di menu Koneksi API."
            }
        return results

    tasks = {}
    if "youtube" in platforms:
        tasks["youtube"] = publish_to_youtube(cfg, filepath, title, script)
    if "instagram" in platforms:
        tasks["instagram"] = publish_to_instagram(cfg, filepath, media_url, title, script)
    if "tiktok" in platforms:
        tasks["tiktok"] = publish_to_tiktok(cfg, filepath, title, script)

    if tasks:
        responses = await asyncio.gather(*tasks.values())
        for name, res in zip(tasks.keys(), responses):
            results[name] = res

    return results