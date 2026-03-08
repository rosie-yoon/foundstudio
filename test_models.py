import google.generativeai as genai

genai.configure(api_key="여기에_본인의_API키_입력")

print("사용 가능한 모델 목록:")
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"✅ {model.name}")
