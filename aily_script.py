import os
import json
import base64
import requests
import zlib
from _sys import logger

# === 配置区域 ===
# 飞书应用配置
FEISHU_APP_ID = "cli_a757be749210500e"
FEISHU_APP_SECRET = "EvAyrNVzqxV7Wp3gET8oA5tjAt1T5ZfJ"

# 上传配置
UPLOAD_PARENT_TOKEN = "WPE1bppuGaTSwTss9sZcDg1vnjh"
UPLOAD_PARENT_TYPE = "bitable_image" 

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
    
    logger.info("正在获取飞书 Access Token...")
    # Aily 环境下访问飞书 API 通常不需要代理，直接访问
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json().get("tenant_access_token")

def upload_to_feishu(token, filepath, file_bytes):
    """
    上传图片到飞书
    """
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
    
    file_size = len(file_bytes)
    checksum = zlib.adler32(file_bytes) & 0xffffffff
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    form_data = {
        "file_name": os.path.basename(filepath),
        "parent_type": UPLOAD_PARENT_TYPE,
        "parent_node": UPLOAD_PARENT_TOKEN,
        "size": str(file_size),
        "checksum": str(checksum)
    }
    
    files = {
        "file": (os.path.basename(filepath), file_bytes, "image/png")
    }

    logger.info(f"正在上传图片到飞书 (Type: {UPLOAD_PARENT_TYPE})...")
    try:
        response = requests.post(url, headers=headers, data=form_data, files=files)
        
        if not response.ok:
            logger.error(f"上传失败 Status: {response.status_code}")
            logger.error(f"响应内容: {response.text}")
            response.raise_for_status()
            
        return response.json()
    except Exception as e:
        logger.error(f"上传过程发生错误: {e}")
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
    
    logger.info(f"正在获取临时下载链接 (File Token: {file_token})...")
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"获取下载链接失败: {e}")
        raise

def main(params):
    """
    Aily 工作流入口函数
    params: 输入的 Base64 字符串
    """
    logger.info("工作流开始执行...")
    
    # 获取输入的 base64 字符串 (直接使用 params)
    b64_data = params
    if not b64_data:
        msg = "错误: 输入参数为空"
        logger.error(msg)
        return {"code": -1, "msg": msg}

    try:
        # 1. 解码图片
        try:
            image_bytes = base64.b64decode(b64_data)
            filename = "input_image.png"
            logger.info(f"图片已解码, 大小: {len(image_bytes)} bytes")
        except Exception as e:
            msg = f"Base64 解码失败: {str(e)}"
            logger.error(msg)
            return {"code": -1, "msg": msg}
        
        # 2. 获取飞书 Token
        feishu_token = get_feishu_token()
        
        # 3. 上传图片
        result = upload_to_feishu(feishu_token, filename, image_bytes)
        
        if result.get("code") != 0:
            msg = f"上传失败: {json.dumps(result)}"
            logger.error(msg)
            return {"code": result.get("code"), "msg": msg}

        file_token = result.get("data", {}).get("file_token")
        logger.info(f"上传成功! File Token: {file_token}")
        
        # 4. 获取临时下载链接
        url_result = get_temp_download_url(feishu_token, file_token)
        
        if url_result.get("code") != 0:
            msg = f"获取链接失败: {json.dumps(url_result)}"
            logger.error(msg)
            return {"code": url_result.get("code"), "msg": msg}
            
        tmp_urls = url_result.get("data", {}).get("tmp_download_urls", [])
        if not tmp_urls:
            msg = "未返回有效的下载链接列表"
            logger.error(msg)
            return {"code": -1, "msg": msg}
            
        tmp_url = tmp_urls[0].get("tmp_download_url")
        logger.info(f"成功获取临时下载链接: {tmp_url}")
        
        # 返回最终结果
        return {
            "file_token": file_token,
            "download_url": tmp_url,
            "status": "success"
        }
            
    except Exception as e:
        logger.error(f"工作流执行异常: {e}")
        return {
            "status": "error",
            "msg": str(e)
        }
