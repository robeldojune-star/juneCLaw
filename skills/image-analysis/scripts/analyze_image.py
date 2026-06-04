#!/usr/bin/env python3
"""
이미지 분석 (Vision API 호출)
- OpenAI (GPT-4V)
- Anthropic (Claude 3 Opus)
- Google (Gemini)
- OpenRouter (무료/유료 모델 지원!)
"""
import sys
import os
import base64
import json
import argparse
from pathlib import Path

def load_env(env_path):
    """ .env 파일에서 환경변수 로드"""
    env_vars = {}
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as e:
        print(f"⚠️ .env 파일 읽기 오류: {e}")
    return env_vars

def encode_image(image_path):
    """이미지를 base64로 인코딩"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_with_openai(image_path, api_key, model, prompt):
    """OpenAI GPT-4V 호출"""
    import requests
    
    base64_image = encode_image(image_path)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4096
    }
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        return f"❌ OpenAI API 오류: {response.status_code} - {response.text}"

def analyze_with_anthropic(image_path, api_key, model, prompt):
    """Anthropic Claude 3 호출"""
    import requests
    
    base64_image = encode_image(image_path)
    media_type = "image/jpeg"
    if image_path.endswith('.png'):
        media_type = "image/png"
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_image
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        return result['content'][0]['text']
    else:
        return f"❌ Anthropic API 오류: {response.status_code} - {response.text}"

def analyze_with_google(image_path, api_key, model, prompt):
    """Google Gemini 호출"""
    import requests
    
    base64_image = encode_image(image_path)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=***"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }
        ]
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    else:
        return f"❌ Google API 오류: {response.status_code} - {response.text}"

def analyze_with_openrouter(image_path, api_key, model, prompt):
    """OpenRouter 모델 호출 (무료 티어 지원!)"""
    import requests
    
    base64_image = encode_image(image_path)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://localhost",  # OpenRouter 요구사항
        "X-Title": "Hermes Image Analysis"
    }
    
    # OpenRouter는 OpenAI 형식과 호환됨
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4096
    }
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        return f"❌ OpenRouter API 오류: {response.status_code} - {response.text}"

def main():
    parser = argparse.ArgumentParser(description='이미지 분석 (Vision API)')
    parser.add_argument('--image', required=True, help='이미지 파일 경로')
    parser.add_argument('--prompt', default='이 이미지를 분석해주세요.', help='분석 요청 프롬프트')
    args = parser.parse_args()
    
    # .env 파일 경로 (trading_workspace)
    env_path = '/home/june/trading_workspace/.env'
    
    # 환경변수 로드
    env_vars = load_env(env_path)
    
    provider = env_vars.get('VISION_PROVIDER', 'openrouter')  # 기본값: openrouter
    model = env_vars.get('VISION_MODEL', 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free')
    api_key = env_vars.get('OPENROUTER_API_KEY') or env_vars.get('OPENAI_API_KEY') or env_vars.get('ANTHROPIC_API_KEY') or env_vars.get('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ API 키가 설정되지 않았습니다.")
        print(f"   .env 파일을 확인해 주세요: {env_path}")
        sys.exit(1)
    
    image_path = args.image
    prompt = args.prompt
    
    if not os.path.exists(image_path):
        print(f"❌ 이미지 파일이 없음: {image_path}")
        sys.exit(1)
    
    print(f"📊 이미지 분석 시작...")
    print(f"   provider: {provider}")
    print(f"   model: {model}")
    print(f"   image: {image_path}")
    print(f"   prompt: {prompt}")
    
    # API 호출
    if provider == 'openai':
        result = analyze_with_openai(image_path, api_key, model, prompt)
    elif provider == 'anthropic':
        result = analyze_with_anthropic(image_path, api_key, model, prompt)
    elif provider == 'google':
        result = analyze_with_google(image_path, api_key, model, prompt)
    elif provider == 'openrouter':
        result = analyze_with_openrouter(image_path, api_key, model, prompt)
    else:
        result = f"❌ 지원하지 않는 provider: {provider}"
    
    print(f"\n📊 분석 결과:")
    print(result)

if __name__ == "__main__":
    main()
