with open('gari_inference_engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

target1 = '''            if p_meta["id"] == "chili":
                diag_res = self.run_chili_disease_model(img)
            else:
                disease_model_dir = p_meta["disease_model_dir"]
                diag_res = self.run_crop_disease_model(img, disease_model_dir, top_k=top_k)'''

replacement1 = '''            disease_model_dir = p_meta.get("disease_model_dir") or "Model tong"
            if p_meta["id"] == "chili":
                diag_res = self.run_chili_disease_model(img)
            else:
                diag_res = self.run_crop_disease_model(img, disease_model_dir, top_k=top_k)'''

target2 = '''                "model_id": f"ConvNeXt-Small ({disease_model_dir})",
                "model_name": f"ConvNeXt-Small ({disease_model_dir})",'''

replacement2 = '''                "model_id": diag_res.get("model_id") or f"ConvNeXt-Small ({disease_model_dir})",
                "model_name": diag_res.get("model_name") or f"ConvNeXt-Small ({disease_model_dir})",'''

text = text.replace(target1.replace('\n', '\r\n'), replacement1.replace('\n', '\r\n'))
text = text.replace(target1, replacement1)

text = text.replace(target2.replace('\n', '\r\n'), replacement2.replace('\n', '\r\n'))
text = text.replace(target2, replacement2)

with open('gari_inference_engine.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed unbound disease_model_dir in gari_inference_engine.py")
