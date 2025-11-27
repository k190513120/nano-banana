import requests
import json

# Configuration
BASE_URL = "https://suspicious-nora-miaomiaocompany-9ba14f3f.koyeb.app"
IMAGE_URL = "https://p3-bot-workflow-sign.byteimg.com/tos-cn-i-mdko3gqilj/8df3562e17bc428985fafe9f5d28fa05.png~tplv-mdko3gqilj-image.image?rk3s=81d4c505&x-expires=1795311120&x-signature=hUJ83LiwRX1Wi%2BHqDIvCJ4%2FvnuU%3D&x-wf-file_name=input_image+%281%29.png"

def test_health():
    print(f"Testing Health Endpoint: {BASE_URL}/health")
    try:
        resp = requests.get(f"{BASE_URL}/health")
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Health check failed: {e}")

def test_generate():
    print(f"\nTesting Generate Endpoint: {BASE_URL}/generate")
    url = f"{BASE_URL}/generate"
    
    # Test with empty parameters to verify default handling
    payload = {
        "prompt": "图片变成白底",
        "imageUrl": IMAGE_URL,
        "aspectRatio": "",
        "imageSize": "",
        "model": "nano banana1"
    }
    
    print("Sending request...")
    try:
        # Set a long timeout because image generation takes time
        resp = requests.post(url, json=payload, timeout=120)
        
        if resp.status_code == 200:
            print("Success! Request completed.")
            try:
                data = resp.json()
                print(f"Response JSON: {json.dumps(data, indent=2)}")
                if "download_url" in data:
                    print(f"Download URL: {data['download_url']}")
            except ValueError:
                print("Response was not JSON. Saving as file just in case...")
                with open("test_koyeb_result.png", "wb") as f:
                    f.write(resp.content)
                print("Saved result to test_koyeb_result.png")
        else:
            print(f"Failed with status {resp.status_code}")
            print(f"Error details: {resp.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_health()
    test_generate()
