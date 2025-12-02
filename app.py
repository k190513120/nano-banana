import os
import base64
import json
import requests
import zlib
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# Version for deployment tracking
VERSION = "1.2.0"
print(f"Starting application version {VERSION}")

# Configuration
# Google Gemini API Key
DEFAULT_API_KEY = "AIzaSyCx6EcRyotOEa-4XFSkEZ6FZD3fKi6apCI"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", DEFAULT_API_KEY)

# Feishu Configuration
FEISHU_APP_ID = "cli_a757be749210500e"
FEISHU_APP_SECRET = "EvAyrNVzqxV7Wp3gET8oA5tjAt1T5ZfJ"
UPLOAD_PARENT_TOKEN = "WPE1bppuGaTSwTss9sZcDg1vnjh"
UPLOAD_PARENT_TYPE = "bitable_image"

# Map user friendly model names to actual API models if needed
MODEL_MAPPING = {
    "nano banana1": "gemini-2.5-flash-image",
    "nano banana2": "gemini-3-pro-image-preview", 
    "default": "gemini-2.5-flash-image"
}

class GenerateRequest(BaseModel):
    aspectRatio: Optional[str] = "1:1"
    aspect_ratio: Optional[str] = None
    imageSize: Optional[str] = "1K"
    image_size: Optional[str] = None
    imageUrl: Optional[str] = None
    image: Optional[str] = None
    prompt: str
    model: str = "nano banana1"

def download_image_as_base64(url: str):
    """Download image from URL and convert to base64 inlineData format"""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        if "image" not in content_type:
            content_type = "image/jpeg"
            
        b64_data = base64.b64encode(resp.content).decode("utf-8")
        return {
            "mimeType": content_type,
            "data": b64_data
        }
    except Exception as e:
        print(f"Failed to download image from {url}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download input image: {str(e)}")

def get_feishu_token():
    """Get Feishu tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    
    print("Getting Feishu Access Token...")
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("tenant_access_token")
    except Exception as e:
        print(f"Failed to get Feishu token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Feishu token: {str(e)}")

def upload_to_feishu(token, filename, file_bytes):
    """Upload image to Feishu"""
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
    
    file_size = len(file_bytes)
    checksum = zlib.adler32(file_bytes) & 0xffffffff
    
    headers = {"Authorization": f"Bearer {token}"}
    
    form_data = {
        "file_name": filename,
        "parent_type": UPLOAD_PARENT_TYPE,
        "parent_node": UPLOAD_PARENT_TOKEN,
        "size": str(file_size),
        "checksum": str(checksum)
    }
    
    files = {
        "file": (filename, file_bytes, "image/png")
    }

    print(f"Uploading image to Feishu (Type: {UPLOAD_PARENT_TYPE})...")
    try:
        response = requests.post(url, headers=headers, data=form_data, files=files)
        if not response.ok:
            print(f"Upload failed Status: {response.status_code}, Body: {response.text}")
            response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Feishu upload failed: {str(e)}")

def get_temp_download_url(token, file_token):
    """Get temporary download URL from Feishu"""
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/batch_get_tmp_download_url"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"file_tokens": file_token}
    
    print(f"Getting temp download URL (File Token: {file_token})...")
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Get download URL failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get download URL: {str(e)}")

@app.post("/generate")
async def generate_image_endpoint(request: GenerateRequest):
    """Generate image using Google Gemini API and upload to Feishu"""
    # Configuration
    DEFAULT_API_KEY = "AIzaSyDvYLrM4Y_J8d0FMaaOx3rWi9RhTgA0e68"
    env_key = os.getenv("GEMINI_API_KEY")
    using_default = False
    
    if not env_key:
        GEMINI_API_KEY = DEFAULT_API_KEY
        using_default = True
    else:
        GEMINI_API_KEY = env_key.strip()
        
    source_str = "DEFAULT" if using_default else "ENV"
    print(f"Loaded GEMINI_API_KEY from {source_str}: {GEMINI_API_KEY[:5]}***")
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Server Configuration Error: GEMINI_API_KEY is not set.")

    # Define model and URL
    api_model = MODEL_MAPPING.get(request.model, "gemini-3-pro-image-preview")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent"
    
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Timing
    t_start = time.time()
    
    # Construct parts
    parts = []
    
    # Normalize input fields (support snake_case aliases)
    final_image_url = request.imageUrl or request.image
    final_aspect_ratio = request.aspectRatio or request.aspect_ratio or "1:1"
    final_image_size = request.imageSize or request.image_size or "1K"
    
    if final_image_url:
        print(f"Downloading image from {final_image_url[:30]}...")
        image_data = download_image_as_base64(final_image_url)
        parts.append({"inlineData": image_data})
        
    t_download = time.time()
    print(f"[Timing] Image Download: {t_download - t_start:.2f}s")
        
    parts.append({"text": request.prompt})
    
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": final_aspect_ratio,
                "imageSize": final_image_size
            }
        }
    }
    
    print(f"Requesting Gemini ({api_model})...")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        t_gemini = time.time()
        print(f"[Timing] Gemini Generation: {t_gemini - t_download:.2f}s")
        
        if not response.ok:
            error_detail = response.text
            print(f"Gemini API Error: {error_detail}")
            key_debug = f"Key starts with: {GEMINI_API_KEY[:5]}... (Source: {source_str})" if GEMINI_API_KEY else "Key is empty"
            raise HTTPException(status_code=response.status_code, detail=f"Gemini API Error: {error_detail}. Debug info: {key_debug}")
            
        data = response.json()
        
        candidates = data.get("candidates", [])
        if not candidates:
            raise HTTPException(status_code=500, detail="Gemini returned no candidates")
            
        content_parts = candidates[0].get("content", {}).get("parts", [])
        image_part = next((p for p in content_parts if "inlineData" in p), None)
        
        if not image_part:
            print("No image in response:", json.dumps(data, indent=2))
            raise HTTPException(status_code=500, detail="No image data found in Gemini response")
            
        b64_data = image_part["inlineData"]["data"]
        image_bytes = base64.b64decode(b64_data)
        
        # --- Feishu Upload Logic ---
        
        # 1. Get Feishu Token
        feishu_token = get_feishu_token()
        t_token = time.time()
        print(f"[Timing] Get Feishu Token: {t_token - t_gemini:.2f}s")
        
        # 2. Upload Image
        filename = "generated_image.png"
        upload_result = upload_to_feishu(feishu_token, filename, image_bytes)
        
        t_upload = time.time()
        print(f"[Timing] Upload to Feishu: {t_upload - t_token:.2f}s")
        
        if upload_result.get("code") != 0:
            raise HTTPException(status_code=500, detail=f"Feishu upload failed: {json.dumps(upload_result)}")
            
        file_token = upload_result.get("data", {}).get("file_token")
        
        # 3. Get Download Link
        url_result = get_temp_download_url(feishu_token, file_token)
        
        t_url = time.time()
        print(f"[Timing] Get Download URL: {t_url - t_upload:.2f}s")
        print(f"[Timing] Total Duration: {t_url - t_start:.2f}s")
        
        if url_result.get("code") != 0:
            raise HTTPException(status_code=500, detail=f"Feishu download URL failed: {json.dumps(url_result)}")
            
        tmp_urls = url_result.get("data", {}).get("tmp_download_urls", [])
        if not tmp_urls:
            raise HTTPException(status_code=500, detail="No download URL returned from Feishu")
            
        download_url = tmp_urls[0].get("tmp_download_url")
        
        return {
            "status": "success",
            "download_url": download_url,
            "file_token": file_token,
            "timing": {
                "download_image": f"{t_download - t_start:.2f}s",
                "gemini_generation": f"{t_gemini - t_download:.2f}s",
                "get_feishu_token": f"{t_token - t_gemini:.2f}s",
                "upload_feishu": f"{t_upload - t_token:.2f}s",
                "get_download_url": f"{t_url - t_upload:.2f}s",
                "total": f"{t_url - t_start:.2f}s"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Internal Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    # Check if we are running with a custom env key
    env_key = os.getenv("GEMINI_API_KEY")
    has_env_key = bool(env_key and env_key.strip())
    return {"status": "ok", "version": VERSION, "has_custom_key": has_env_key}

@app.get("/")
def root():
    # Check if we are running with a custom env key
    env_key = os.getenv("GEMINI_API_KEY")
    has_env_key = bool(env_key and env_key.strip())
    return {
        "message": "Service is running", 
        "version": VERSION, 
        "has_custom_key": has_env_key,
        "note": "Please set GEMINI_API_KEY in Koyeb Environment Variables if has_custom_key is false"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
