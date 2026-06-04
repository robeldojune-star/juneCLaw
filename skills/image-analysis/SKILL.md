---
name: image-analysis
description: "이미지 분석 (차트, 그래프, 스크린샷). 외부 Vision API(GPT-4V, Claude 3, Gemini) 호출."
---
# 이미지 분석 스킬 (Vision API)
- OpenAI (GPT-4V)
- Anthropic (Claude 3 Opus)
- Google (Gemini 2.5 Pro)  # 최신 모델!
- OpenRouter (다양한 무료/유료 Vision-Language 모델 지원, 예: nvidia/nemotron-nano-12b-v2-vl:free)
3. 분석 결과 반환 (JSON/텍스트)

## 사용 방법

### 1. API 키 설정 (.env)
```bash
# OpenAI (GPT-4V)
VISION_PROVIDER=openai
VISION_MODEL=gpt-4-turbo
OPENAI_API_KEY=sk-...

# Anthropic (Claude 3 Opus)
VISION_PROVIDER=anthropic
VISION_MODEL=claude-3-opus-20240229
ANTHROPIC_API_KEY=sk-ant-...

# Google (Gemini Pro Vision)
VISION_PROVIDER=google
VISION_MODEL=gemini-pro-vision
GOOGLE_API_KEY=AIza...

# OpenRouter (다양한 무료/유료 모델)
VISION_PROVIDER=openrouter
VISION_MODEL=nvidia/nemotron-nano-12b-v2-vl:free
OPENROUTER_API_KEY=sk-or-...
```

### 2. 스크립트 실행
```bash
python3 scripts/analyze_image.py --image <이미지경로> --prompt "차트 분석 요청"
```

## 스크립트: `scripts/analyze_image.py`

```python
#!/usr/bin/env python3
"""
이미지 분석 (Vision API 호출)
- OpenAI GPT-4V
- Anthropic Claude 3 Opus
- Google Gemini Pro Vision
"""
import sys
import os
import base64
import json
import argparse
from pathlib import Path

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
    """Google Gemini Pro Vision 호출"""
    import requests
    
    base64_image = encode_image(image_path)
    
    url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"
    
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

def main():
    parser = argparse.ArgumentParser(description='이미지 분석 (Vision API)')
    parser.add_argument('--image', required=True, help='이미지 파일 경로')
    parser.add_argument('--prompt', default='이 이미지를 분석해주세요.', help='분석 요청 프롬프트')
    args = parser.parse_args()
    
    # API 키 로드
    provider = os.getenv('VISION_PROVIDER', 'openai')
    model = os.getenv('VISION_MODEL', 'gpt-4-turbo')
    
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
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ OPENAI_API_KEY가 설정되지 않았습니다.")
            sys.exit(1)
        result = analyze_with_openai(image_path, api_key, model, prompt)
    elif provider == 'anthropic':
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
            sys.exit(1)
        result = analyze_with_anthropic(image_path, api_key, model, prompt)
    elif provider == 'google':
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            print("❌ GOOGLE_API_KEY가 설정되지 않았습니다.")
            sys.exit(1)
        result = analyze_with_google(image_path, api_key, model, prompt)
    else:
        print(f"❌ 지원하지 않는 provider: {provider}")
        sys.exit(1)
    
    print(f"\n📊 분석 결과:")
    print(result)

if __name__ == "__main__":
    main()
```

## 사용 예시

### 삼성전자 차트 분석
```bash
python3 scripts/analyze_image.py \\
  --image /home/june/trading_workspace/Screenshot_20260528_072247_S_.jpg \\
  --prompt "이 차트에서 매수 신호와 매도 신호가 적절한 위치에 있는지 분석해주세요. 고점에서 매수했거나 저점에서 매도하지 않았는지 확인해주세요."
```

## 주의사항
1. API 키가 필요합니다 (.env에 설정)
2. 이미지 파일 크기 제한이 있을 수 있습니다 (OpenAI: 20MB)
3. API 호출 비용이 발생할 수 있습니다.

## 다음 단계
1. .env에 VISION_PROVIDER, VISION_MODEL, API 키 설정
2. pip install requests (아직 안 됨 경우)
3. 스크립트 실행해서 이미지 분석
4. 분석 결과를 바탕으로 차트 비교/개선