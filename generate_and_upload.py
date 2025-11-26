import os
import json
import base64
import requests
import zlib
import sys

# === 配置区域 ===

# Google Gemini API Key
# 优先读取环境变量，如果没有则使用硬编码的 Key (开发测试用)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    GEMINI_API_KEY = "AIzaSyDvYLrM4Y_J8d0FMaaOx3rWi9RhTgA0e68"

# 飞书应用配置
FEISHU_APP_ID = "cli_a757be749210500e"
FEISHU_APP_SECRET = "EvAyrNVzqxV7Wp3gET8oA5tjAt1T5ZfJ"

# 上传配置
UPLOAD_PARENT_TOKEN = "WPE1bppuGaTSwTss9sZcDg1vnjh"
UPLOAD_PARENT_TYPE = "bitable_image" # 用户指定为 bitable_image

def generate_image():
    """
    调用 Google Gemini 模型生成图片
    """
    if not GEMINI_API_KEY:
        print("错误: 未找到 GEMINI_API_KEY 环境变量。")
        print("请在运行前执行: export GEMINI_API_KEY='你的key'")
        sys.exit(1)

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent"
    
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }
    
    # 构建请求体
    payload = {
        "contents": [{"parts": [{"text": "Da Vinci style anatomical sketch of a dissected Monarch butterfly. Detailed drawings of the head, wings, and legs on textured parchment with notes in English."}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "1:1", "imageSize": "1K"}
        }
    }

    print(f"正在请求 Gemini 生成图片...")
    try:
        # 使用代理访问 Google API
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Gemini 请求失败: {e}")
        if 'response' in locals():
            print(response.text)
        raise

    # 解析响应提取 Base64 图片
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini 未返回任何 candidates")
            
        parts = candidates[0].get("content", {}).get("parts", [])
        
        # 寻找包含 inlineData 的部分
        image_part = next((p for p in parts if "inlineData" in p), None)
        
        if not image_part:
            # 有时候可能因为安全原因被拦截，打印出来看看
            print("未在响应中找到图片数据。响应内容:")
            print(json.dumps(data, indent=2))
            raise ValueError("未找到图片数据")
            
        b64_data = image_part["inlineData"]["data"]
        image_bytes = base64.b64decode(b64_data)
        
        # 在内存中处理，不保存文件
        filename = "butterfly.png" # 设置一个虚拟文件名用于上传
        print(f"图片已生成 (内存中), 大小: {len(image_bytes)} bytes")
        
        # 返回 base64 数据以便调试或复用
        return filename, image_bytes, b64_data
        
    except Exception as e:
        print(f"解析图片数据失败: {e}")
        raise

def get_feishu_token():
    """
    获取飞书 tenant_access_token
    """
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    
    print("正在获取飞书 Access Token...")
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json().get("tenant_access_token")

def upload_to_feishu(token, filepath, file_bytes):
    """
    上传图片到飞书
    """
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
    
    file_size = len(file_bytes)
    # 计算 adler32 checksum (虽然是可选的，但加上更规范)
    checksum = zlib.adler32(file_bytes) & 0xffffffff
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # 构造 multipart/form-data 的 data 部分
    # 注意: bitable_image 通常直接使用 parent_node 传递 token
    form_data = {
        "file_name": os.path.basename(filepath),
        "parent_type": UPLOAD_PARENT_TYPE,
        "parent_node": UPLOAD_PARENT_TOKEN,
        "size": str(file_size),
        "checksum": str(checksum)
    }
    
    # 构造文件部分
    files = {
        "file": (os.path.basename(filepath), file_bytes, "image/png")
    }

    print(f"正在上传图片到飞书 (Type: {UPLOAD_PARENT_TYPE})...")
    try:
        response = requests.post(url, headers=headers, data=form_data, files=files)
        
        if not response.ok:
            print(f"上传失败 Status: {response.status_code}")
            print(f"响应内容: {response.text}")
            response.raise_for_status()
            
        return response.json()
    except Exception as e:
        print(f"上传过程发生错误: {e}")
        raise

def get_temp_download_url(token, file_token):
    """
    获取图片临时下载链接
    """
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/batch_get_tmp_download_url"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "file_tokens": file_token
    }
    
    print(f"正在获取临时下载链接 (File Token: {file_token})...")
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"获取下载链接失败: {e}")
        raise

def main():
    try:
        # 1. 生成图片
        filename, img_bytes, b64_str = generate_image()
        
        print("\n=== Base64 字符串 (可用于 Aily 工作流) ===")
        # 补全 padding (虽然 Google API 返回的通常是标准的，但为了保险)
        missing_padding = len(b64_str) % 4
        if missing_padding:
            b64_str += '=' * (4 - missing_padding)
        print(b64_str)
        print("========================================\n")
        
        # 2. 获取飞书 Token
        feishu_token = get_feishu_token()
        
        # 3. 上传图片
        result = upload_to_feishu(feishu_token, filename, img_bytes)
        
        print("\n=== 处理完成 ===")
        if result.get("code") == 0:
            file_token = result.get("data", {}).get("file_token")
            print(f"上传成功!")
            print(f"File Token: {file_token}")
            
            # 4. 获取临时下载链接
            url_result = get_temp_download_url(feishu_token, file_token)
            if url_result.get("code") == 0:
                tmp_urls = url_result.get("data", {}).get("tmp_download_urls", [])
                if tmp_urls:
                    tmp_url = tmp_urls[0].get("tmp_download_url")
                    print(f"\n临时下载链接: {tmp_url}")
                else:
                    print(f"未获取到下载链接: {json.dumps(url_result, ensure_ascii=False)}")
            else:
                print(f"获取下载链接失败 (API返回错误): {json.dumps(url_result, ensure_ascii=False)}")
                
            print("\n完整上传响应:", json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("上传虽然完成但返回了错误码:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"\n任务失败: {e}")

if __name__ == "__main__":
    main()
