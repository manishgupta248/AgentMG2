"""Google Drive tools — list/search, upload, download, create folder."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.core.google_auth import get_google_service
from app.core.exceptions import GoogleAPIError, ToolExecutionError


class DriveSearchInput(BaseModel):
    query: str = Field("", description="Drive search query, e.g. \"name contains 'invoice'\". Empty lists recent files.")
    max_results: int = Field(10, ge=1, le=50)
    model_config = {"extra": "forbid"}


@tool(
    "drive_search",
    permission=PermissionLevel.READ,
    description="Searches or lists files in Google Drive.",
    input_schema=DriveSearchInput,
    example_phrases=["search my drive files", "find file in google drive"],
)
def drive_search(query: str = "", max_results: int = 10) -> dict:
    try:
        service = get_google_service("drive")
        params = {"pageSize": max_results, "fields": "files(id, name, mimeType, modifiedTime, size)"}
        if query:
            params["q"] = query
        results = service.files().list(**params).execute()
        return {"count": len(results.get("files", [])), "files": results.get("files", [])}
    except Exception as e:
        raise GoogleAPIError(f"Drive search failed: {e}", context={"query": query}) from e


class DriveUploadInput(BaseModel):
    local_file_path: str
    drive_filename: str | None = Field(None, description="Filename to use in Drive; defaults to the local filename")
    folder_id: str | None = Field(None, description="Parent folder ID; omit to upload to Drive root")
    model_config = {"extra": "forbid"}


@tool(
    "drive_upload_file",
    permission=PermissionLevel.MODIFY,
    description="Uploads a local file to Google Drive.",
    input_schema=DriveUploadInput,
    example_phrases=["upload this file to drive", "save file to google drive"],
)
def drive_upload_file(local_file_path: str, drive_filename: str | None = None, folder_id: str | None = None) -> dict:
    path = Path(local_file_path)
    if not path.exists():
        raise ToolExecutionError(f"Local file not found: {local_file_path}", context={"local_file_path": local_file_path})

    try:
        service = get_google_service("drive")
        file_metadata = {"name": drive_filename or path.name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(str(path), resumable=True)
        uploaded = service.files().create(body=file_metadata, media_body=media, fields="id, name, webViewLink").execute()
        return {"file_id": uploaded["id"], "name": uploaded["name"], "link": uploaded.get("webViewLink")}
    except Exception as e:
        raise GoogleAPIError(f"Drive upload failed: {e}", context={"local_file_path": local_file_path}) from e


class DriveDownloadInput(BaseModel):
    file_id: str
    save_to_path: str
    model_config = {"extra": "forbid"}


@tool(
    "drive_download_file",
    permission=PermissionLevel.READ,
    description="Downloads a file from Google Drive to a local path.",
    input_schema=DriveDownloadInput,
    example_phrases=["download this file from drive", "get file from google drive"],
)
def drive_download_file(file_id: str, save_to_path: str) -> dict:
    try:
        service = get_google_service("drive")
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        save_path = Path(save_to_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(fh.getvalue())

        return {"file_id": file_id, "saved_to": str(save_path), "size_bytes": save_path.stat().st_size}
    except Exception as e:
        raise GoogleAPIError(f"Drive download failed: {e}", context={"file_id": file_id}) from e


class DriveCreateFolderInput(BaseModel):
    folder_name: str
    parent_folder_id: str | None = None
    model_config = {"extra": "forbid"}


@tool(
    "drive_create_folder",
    permission=PermissionLevel.MODIFY,
    description="Creates a new folder in Google Drive.",
    input_schema=DriveCreateFolderInput,
    example_phrases=["create a folder in drive", "make a new google drive folder"],
)
def drive_create_folder(folder_name: str, parent_folder_id: str | None = None) -> dict:
    try:
        service = get_google_service("drive")
        metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]
        folder = service.files().create(body=metadata, fields="id, name").execute()
        return {"folder_id": folder["id"], "name": folder["name"]}
    except Exception as e:
        raise GoogleAPIError(f"Drive folder creation failed: {e}", context={"folder_name": folder_name}) from e