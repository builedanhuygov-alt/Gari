import urllib.request
import json

data = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/api/models').read().decode())
models = data.get('models', [])
print(f"Total models reported: {len(models)}")

kinds = {}
archs = {}
for m in models:
    k = m.get('kind', 'unknown')
    a = m.get('arch', 'unknown')
    kinds[k] = kinds.get(k, 0) + 1
    archs[a] = archs.get(a, 0) + 1

print("Kinds breakdown:", kinds)
print("Architectures breakdown:", archs)
print("\nDetailed list:")
for i, m in enumerate(models):
    cid = m.get('crop_id')
    k = m.get('kind')
    a = m.get('arch')
    cls_cnt = m.get('classes_count')
    mb = m.get('weight_size_mb')
    acc = m.get('accuracy')
    print(f"{i+1:2d}. {cid:22} | kind={k:12} | arch={a:16} | classes={cls_cnt:2d} | size={mb:6.2f}MB | acc={acc}")

