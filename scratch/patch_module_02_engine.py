from pathlib import Path

path = Path("gari_inference_engine.py")
content = path.read_text(encoding="utf-8")

# 1. Update PRIORITY_CROPS chili configuration to indicate disease model available via Model tong
old_priority_crops = """    "chili": {
        "id": "chili",
        "name_vi": "Ớt",
        "name_en": "Chili",
        "has_disease_model": False,
        "disease_model_dir": None,
        "arch": None,
        "aliases": ["chili", "chilli", "ớt", "ot", "pepper_bell", "pepper,_bell"]
    },"""

new_priority_crops = """    "chili": {
        "id": "chili",
        "name_vi": "Ớt",
        "name_en": "Chili",
        "has_disease_model": True,
        "disease_model_dir": "Model tong",
        "arch": "vit_base",
        "classes": ["Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy"],
        "aliases": ["chili", "chilli", "ớt", "ot", "pepper_bell", "pepper,_bell", "ớt cay", "ớt ngọt", "ớt chuông"]
    },"""

content = content.replace(old_priority_crops.replace("\r\n", "\n"), new_priority_crops.replace("\r\n", "\n"))
content = content.replace(old_priority_crops, new_priority_crops)

# 2. Add run_chili_disease_model method in GariInferenceEngine
old_run_crop = """        return {
            "disease_id": best_class,
            "disease_name_vi": best_name_vi,
            "disease_score": best_conf,
            "top_predictions": top_predictions,
            "model_name": f"ConvNeXt-Small ({model_dir_name})",
            "model_id": f"ConvNeXt-Small ({model_dir_name})",
            "model_arch": entry.arch,
            "localization": localization_bundle,
            "entry": entry
        }"""

new_run_crop = """        return {
            "disease_id": best_class,
            "disease_name_vi": best_name_vi,
            "disease_score": best_conf,
            "top_predictions": top_predictions,
            "model_name": f"ConvNeXt-Small ({model_dir_name})",
            "model_id": f"ConvNeXt-Small ({model_dir_name})",
            "model_arch": entry.arch,
            "localization": localization_bundle,
            "entry": entry
        }

    def run_chili_disease_model(self, img: Image.Image) -> Dict[str, Any]:
        \"\"\"
        Runs PlantVillage Model tong specifically focused on Chili / Bell Pepper pathology:
        - Pepper,_bell___Bacterial_spot (Bệnh đốm vi khuẩn trên ớt)
        - Pepper,_bell___healthy (Lá ớt khỏe mạnh)
        \"\"\"
        net, entry = self.load_model("Model tong")
        tensor = entry.preprocess(img).to(self.device)
        with torch.no_grad():
            out = net(tensor)
            logits = out.logits if hasattr(out, "logits") else out
            
        # Find indices for pepper classes
        chili_indices = [i for i, c in enumerate(entry.classes) if "pepper" in c.lower()]
        if not chili_indices:
            probs = torch.softmax(logits, dim=1)[0]
            best_idx = torch.argmax(probs).item()
            best_class = entry.classes[best_idx]
            best_score = float(probs[best_idx])
            top_predictions = [{
                "class_id": best_class,
                "label": localize_disease(best_class),
                "name_vi": localize_disease(best_class),
                "confidence": round(best_score, 4),
                "confidence_percent": round(best_score * 100, 2)
            }]
        else:
            chili_logits = logits[0, chili_indices]
            chili_probs = torch.softmax(chili_logits, dim=0)
            best_local_idx = torch.argmax(chili_probs).item()
            best_idx = chili_indices[best_local_idx]
            best_class = entry.classes[best_idx]
            best_score = float(chili_probs[best_local_idx])
            top_predictions = []
            for l_idx, p_val in enumerate(chili_probs.tolist()):
                c_idx = chili_indices[l_idx]
                c_name = entry.classes[c_idx]
                c_label = localize_disease(c_name)
                top_predictions.append({
                    "class_id": c_name,
                    "label": c_label,
                    "name_vi": c_label,
                    "confidence": round(p_val, 4),
                    "confidence_percent": round(p_val * 100, 2)
                })
            top_predictions.sort(key=lambda x: x["confidence"], reverse=True)

        name_vi = localize_disease(best_class)
        return {
            "disease_id": best_class,
            "disease_name_vi": name_vi,
            "disease_score": best_score,
            "top_predictions": top_predictions,
            "model_name": "Model tong (ViT PlantVillage - Chili/Pepper)",
            "model_id": "Model tong (ViT PlantVillage)",
            "model_arch": entry.arch,
            "localization": None,
            "entry": entry
        }"""

content = content.replace(old_run_crop.replace("\r\n", "\n"), new_run_crop.replace("\r\n", "\n"))
content = content.replace(old_run_crop, new_run_crop)

# 3. Update predict() in manual mode to use run_chili_disease_model for chili
old_manual_predict = """            # Crop has verified disease model (Coffee, Black_Pepper, Rice, Tomato, Maize)
            disease_model_dir = p_meta["disease_model_dir"]
            diag_res = self.run_crop_disease_model(img, disease_model_dir, top_k=top_k)"""

new_manual_predict = """            # Crop has verified disease model (Coffee, Black_Pepper, Rice, Tomato, Maize, Chili)
            if p_meta["id"] == "chili":
                diag_res = self.run_chili_disease_model(img)
            else:
                disease_model_dir = p_meta["disease_model_dir"]
                diag_res = self.run_crop_disease_model(img, disease_model_dir, top_k=top_k)"""

content = content.replace(old_manual_predict.replace("\r\n", "\n"), new_manual_predict.replace("\r\n", "\n"))
content = content.replace(old_manual_predict, new_manual_predict)

path.write_text(content, encoding="utf-8")
print("gari_inference_engine.py patched successfully for Module 02.")
