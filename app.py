import os
import base64
import json
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# Version for deployment tracking
VERSION = "1.0.2"
print(f"Starting application version {VERSION}")

# Configuration
# Default to the key provided by user if not in env
DEFAULT_API_KEY = "AIzaSyDvYLrM4Y_J8d0FMaaOx3rWi9RhTgA0e68"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", DEFAULT_API_KEY)

# Map user friendly model names to actual API models if needed
# Currently both map to gemini-3-pro-image-preview as that's what we have
MODEL_MAPPING = {
    "nano banana1": "gemini-3-pro-image-preview",
    "nano banana2": "gemini-3-pro-image-preview", # Assuming same for now
    "default": "gemini-3-pro-image-preview"
}

class GenerateRequest(BaseModel):
    aspectRatio: str = "1:1"
    imageSize: str = "1K"  # Corresponds to 'clarity'
    imageUrl: Optional[str] = None
    prompt: str
    model: str = "nano banana1"

def download_image_as_base64(url: str):
    """
    Download image from URL and convert to base64 inlineData format
    """
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        # Ensure compatible mime type (image/jpeg, image/png, image/webp)
        if "image" not in content_type:
            content_type = "image/jpeg" # Fallback
            
        b64_data = base64.b64encode(resp.content).decode("utf-8")
        return {
            "mimeType": content_type,
            "data": b64_data
        }
    except Exception as e:
        print(f"Failed to download image from {url}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download input image: {str(e)}")

@app.post("/generate")
async def generate_image_endpoint(request: GenerateRequest):
    """
    Generate image using Google Gemini API
    """
    # Configuration
    # Default to the key provided by user if not in env
    DEFAULT_API_KEY = "AIzaSyDvYLrM4Y_J8d0FMaaOx3rWi9RhTgA0e68"
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", DEFAULT_API_KEY)
    
    # 强制打印一下Key的前几位，方便在Koyeb日志里确认
    print(f"Loaded GEMINI_API_KEY: {GEMINI_API_KEY[:5]}***")
    
    # Define model and URL
    api_model = MODEL_MAPPING.get(request.model, "gemini-3-pro-image-preview")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent"
    
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Construct parts
    parts = []
    
    # If image URL is provided, add it to parts for multimodal input (usually image first context)
    if request.imageUrl:
        image_data = download_image_as_base64(request.imageUrl)
        parts.append({"inlineData": image_data})
        
    parts.append({"text": request.prompt})
    
    payload = {
        "contents": [{"parts": parts}],
        "tools": [{"google_search": {}}], # Keep google_search as in original script
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {
                "aspectRatio": request.aspectRatio,
                "imageSize": request.imageSize
            }
        }
    }
    
    print(f"Requesting Gemini ({api_model})...")
    
    try:
        # No proxy for cloud deployment usually
        response = requests.post(url, headers=headers, json=payload)
        
        if not response.ok:
            error_detail = response.text
            print(f"Gemini API Error: {error_detail}")
            raise HTTPException(status_code=response.status_code, detail=f"Gemini API Error: {error_detail}")
            
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
        
        return Response(content=image_bytes, media_type="image/png")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Internal Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "version": VERSION}

@app.get("/")
def root():
    return {"message": "Service is running", "version": VERSION}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
