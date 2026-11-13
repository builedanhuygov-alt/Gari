import os
import json

crops = ['Tomato', 'Rice', 'Coffee', 'Black_Pepper', 'Maize', 'Model tong']

for crop in crops:
    p = os.path.join('models', crop)
    if os.path.exists(p):
        files = os.listdir(p)
        print(f"=== {crop} ===")
        print("  Files:", files[:8])
        for meta in ['config.json', 'classes.json', 'labels.json', 'model_info.json', 'class_names.json']:
            mp = os.path.join(p, meta)
            if os.path.exists(mp):
                try:
                    with open(mp, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            print(f"  {meta}: list of {len(data)} items: {data[:4]}...")
                        elif isinstance(data, dict):
                            keys = list(data.keys())
                            num_classes = len(data.get("classes", [])) or len(data.get("labels", [])) or len(data.get("id2label", []))
                            arch = data.get("architectures") or data.get("model_type") or data.get("architecture")
                            print(f"  {meta}: arch={arch}, classes count={num_classes}")
                except Exception as e:
                    print(f"  {meta}: error {e}")

