import sys
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_inference_engine

# engine test
engine = gari_inference_engine.GariInferenceEngine()

print("=" * 60)
print("1. PlantVillage Tomato Bacterial Spot Images")
print("=" * 60)
tomato_dir = ROOT_DIR / "data" / "organized" / "PlantVillage" / "Tomato_Bacterial_spot"
if tomato_dir.exists():
    for p in list(tomato_dir.glob("*.JPG"))[:5]:
        img = Image.open(p)
        gate = gari_inference_engine.validate_leaf_gate(img)
        print(f"{p.name}: status={gate['status']}, score={gate['score']}")
        m = gate['metrics']
        print(f"   metrics: green={m.get('green_ratio')}, yellow={m.get('yellow_ratio')}, brown={m.get('brown_ratio')}, botanical={m.get('botanical_ratio')}, exg={m.get('mean_exg')}")

print("\n" + "=" * 60)
print("2. Test Leaf Fixture")
print("=" * 60)
test_leaf = ROOT_DIR / "tests" / "fixtures" / "test_leaf.jpg"
if test_leaf.exists():
    img = Image.open(test_leaf)
    gate = gari_inference_engine.validate_leaf_gate(img)
    print(f"test_leaf.jpg: status={gate['status']}, score={gate['score']}")
    m = gate['metrics']
    print(f"   metrics: green={m.get('green_ratio')}, yellow={m.get('yellow_ratio')}, brown={m.get('brown_ratio')}, botanical={m.get('botanical_ratio')}, exg={m.get('mean_exg')}")

print("\n" + "=" * 60)
print("3. Field Dataset Images")
print("=" * 60)
field_dir = ROOT_DIR / "data" / "field_dataset" / "images"
if field_dir.exists():
    for p in list(field_dir.glob("*.*"))[:5]:
        img = Image.open(p)
        gate = gari_inference_engine.validate_leaf_gate(img)
        print(f"{p.name}: status={gate['status']}, score={gate['score']}")
        m = gate['metrics']
        print(f"   metrics: green={m.get('green_ratio')}, yellow={m.get('yellow_ratio')}, brown={m.get('brown_ratio')}, botanical={m.get('botanical_ratio')}, exg={m.get('mean_exg')}")

print("\n" + "=" * 60)
print("4. Test Samples 17 (Non-leaf, etc.)")
print("=" * 60)
samples_dir = ROOT_DIR / "data" / "test_samples_17"
if samples_dir.exists():
    for p in list(samples_dir.glob("*.jpg")):
        img = Image.open(p)
        gate = gari_inference_engine.validate_leaf_gate(img)
        print(f"{p.name}: status={gate['status']}, score={gate['score']}")
        m = gate['metrics']
        print(f"   metrics: green={m.get('green_ratio')}, yellow={m.get('yellow_ratio')}, brown={m.get('brown_ratio')}, botanical={m.get('botanical_ratio')}, exg={m.get('mean_exg')}")
