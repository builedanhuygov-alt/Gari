import os
import sys
import json
import uuid
import time
import shutil
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from PIL import Image

FIELD_DATASET_DIR = Path(r"D:\leaf-diseases-detector-main\data\field_dataset")
IMAGES_DIR = FIELD_DATASET_DIR / "images"
ANNOTATIONS_FILE = FIELD_DATASET_DIR / "field_annotations.json"
MODELS_DIR = Path(r"D:\leaf-diseases-detector-main\models")

# Key focus crops for Vietnam agricultural readiness
VIETNAM_KEY_CROPS = {
    "Coffee": {"name_vi": "Cà phê", "scientific": "Coffea canephora / arabica", "model_id": "Coffee"},
    "Black_Pepper": {"name_vi": "Hồ tiêu", "scientific": "Piper nigrum", "model_id": "Black_Pepper"},
    "Rice": {"name_vi": "Lúa", "scientific": "Oryza sativa", "model_id": "Rice"},
    "Durian": {"name_vi": "Sầu riêng", "scientific": "Durio zibethinus", "model_id": None},
    "Rubber": {"name_vi": "Cao su", "scientific": "Hevea brasiliensis", "model_id": None},
    "Dragon_Fruit": {"name_vi": "Thanh long", "scientific": "Hylocereus undatus", "model_id": None},
    "Tomato": {"name_vi": "Cà chua", "scientific": "Solanum lycopersicum", "model_id": "Tomato"},
    "Potato": {"name_vi": "Khoai tây", "scientific": "Solanum tuberosum", "model_id": "Potato"},
}

def compute_iou_and_dice(mask_pred: np.ndarray, mask_gt: np.ndarray) -> Dict[str, float]:
    """
    Computes Intersection over Union (IoU / Jaccard) and Dice Coefficient (F1)
    between binary prediction and ground-truth masks.
    """
    pred_bin = (mask_pred > 0).astype(np.uint8)
    gt_bin = (mask_gt > 0).astype(np.uint8)

    intersection = float(np.logical_and(pred_bin, gt_bin).sum())
    union = float(np.logical_or(pred_bin, gt_bin).sum())
    pred_sum = float(pred_bin.sum())
    gt_sum = float(gt_bin.sum())

    if union == 0:
        iou = 1.0 if (pred_sum == 0 and gt_sum == 0) else 0.0
    else:
        iou = intersection / union

    denom = pred_sum + gt_sum
    if denom == 0:
        dice = 1.0 if (pred_sum == 0 and gt_sum == 0) else 0.0
    else:
        dice = (2.0 * intersection) / denom

    return {
        "iou": round(iou, 4),
        "dice": round(dice, 4),
        "intersection_px": int(intersection),
        "union_px": int(union),
        "pred_area_px": int(pred_sum),
        "gt_area_px": int(gt_sum)
    }

class FieldDatasetManager:
    def __init__(self, dataset_dir: Path = FIELD_DATASET_DIR):
        self.dataset_dir = dataset_dir
        self.images_dir = dataset_dir / "images"
        self.annotations_file = dataset_dir / "field_annotations.json"
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.records: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self.annotations_file.exists():
            try:
                with open(self.annotations_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.records = {r["id"]: r for r in data if "id" in r}
                    elif isinstance(data, dict):
                        self.records = data
            except Exception as e:
                print(f"[WARNING] Failed to load {self.annotations_file}: {e}")
                self.records = {}
        else:
            self.records = {}

    def save(self):
        with open(self.annotations_file, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def check_model_exists(self, crop_id: str) -> bool:
        if not crop_id or crop_id in ["Unknown", "Other"]:
            return False
        # Check canonical directory
        cand_dir = MODELS_DIR / crop_id
        if cand_dir.exists() and (cand_dir / "config.json").exists():
            return True
        # Check aliases
        if crop_id == "Black_Pepper" and (MODELS_DIR / "Black_Pepper").exists():
            return True
        return False

    def add_image(
        self,
        src_image_path: str,
        crop_id: str,
        crop_name_vi: str,
        health_status: str,
        disease_id: Optional[str] = None,
        disease_name_vi: Optional[str] = None,
        environment: str = "outdoor_field",
        lighting: str = "natural_sunlight",
        capture_view: str = "single_leaf_top",
        device_type: str = "smartphone",
        province: str = "Đắk Lắk",
        district: str = "Cư M'gar",
        agro_zone: str = "Tây Nguyên (Central Highlands)",
        source_type: str = "vietnam_field_collection",
        contributor: str = "Agronomist",
        session_id: Optional[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Ingests an image into the field validation dataset with complete metadata.
        """
        record_id = f"field_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        src_path = Path(src_image_path)
        if not src_path.exists():
            raise FileNotFoundError(f"Source image not found: {src_image_path}")

        # Compute MD5
        with open(src_path, "rb") as f:
            raw_bytes = f.read()
            md5_hash = hashlib.md5(raw_bytes).hexdigest()

        # Open to verify and extract dimensions
        with Image.open(src_path) as im:
            width, height = im.size
            fmt = im.format or "JPEG"

        # Copy image to dataset store
        ext = src_path.suffix.lower() if src_path.suffix else ".jpg"
        dest_filename = f"{record_id}_{crop_id.lower()}{ext}"
        dest_path = self.images_dir / dest_filename
        shutil.copy2(src_path, dest_path)

        model_exists = self.check_model_exists(crop_id)

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record = {
            "id": record_id,
            "filename": dest_filename,
            "filepath": f"images/{dest_filename}",
            "image_metadata": {
                "width": width,
                "height": height,
                "channels": 3,
                "file_size_bytes": len(raw_bytes),
                "format": fmt,
                "md5_checksum": md5_hash
            },
            "crop": {
                "crop_id": crop_id,
                "crop_name_vi": crop_name_vi,
                "scientific_name": VIETNAM_KEY_CROPS.get(crop_id, {}).get("scientific", ""),
                "compatible_model_exists": model_exists
            },
            "health_status": health_status,
            "diagnosis": {
                "disease_id": disease_id if health_status == "abnormal" else None,
                "disease_name_vi": disease_name_vi if health_status == "abnormal" else None,
                "is_verified": False,
                "confidence_level": "suspected" if disease_id else "unknown"
            },
            "capture_conditions": {
                "environment": environment,
                "lighting": lighting,
                "capture_view": capture_view,
                "device_type": device_type
            },
            "location": {
                "province": province,
                "district": district,
                "agro_ecological_zone": agro_zone
            },
            "source": {
                "source_type": source_type,
                "contributor_id": contributor,
                "session_id": session_id or f"sess_{time.strftime('%Y%m%d')}"
            },
            "localization": {
                "has_manual_annotations": False,
                "bounding_boxes": [],
                "polygons": [],
                "mask_file": None
            },
            "annotation_status": "pending",
            "reviewer_audit": {
                "reviewer_id": None,
                "reviewer_name": None,
                "reviewed_at": None,
                "notes": notes,
                "dispute_reason": None
            },
            "created_at": now_iso,
            "updated_at": now_iso
        }

        self.records[record_id] = record
        self.save()
        return record

    def update_review(
        self,
        record_id: str,
        reviewer_id: str,
        reviewer_name: str,
        status: str,
        corrected_crop_id: Optional[str] = None,
        corrected_crop_name_vi: Optional[str] = None,
        corrected_disease_id: Optional[str] = None,
        corrected_disease_name_vi: Optional[str] = None,
        health_status: Optional[str] = None,
        notes: str = "",
        dispute_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Updates reviewer verification, corrections, or disputes.
        """
        if record_id not in self.records:
            raise KeyError(f"Record {record_id} not found.")

        rec = self.records[record_id]
        rec["annotation_status"] = status
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if corrected_crop_id:
            rec["crop"]["crop_id"] = corrected_crop_id
            rec["crop"]["crop_name_vi"] = corrected_crop_name_vi or corrected_crop_id
            rec["crop"]["compatible_model_exists"] = self.check_model_exists(corrected_crop_id)

        if health_status:
            rec["health_status"] = health_status

        if corrected_disease_id is not None:
            rec["diagnosis"]["disease_id"] = corrected_disease_id
            rec["diagnosis"]["disease_name_vi"] = corrected_disease_name_vi
            rec["diagnosis"]["is_verified"] = (status == "verified")
            rec["diagnosis"]["confidence_level"] = "field_verified" if status == "verified" else "suspected"

        rec["reviewer_audit"] = {
            "reviewer_id": reviewer_id,
            "reviewer_name": reviewer_name,
            "reviewed_at": now_iso,
            "notes": notes,
            "dispute_reason": dispute_reason
        }
        rec["updated_at"] = now_iso

        self.save()
        return rec

    def add_localization(
        self,
        record_id: str,
        bounding_boxes: Optional[List[Dict[str, Any]]] = None,
        polygons: Optional[List[Dict[str, Any]]] = None,
        mask_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Attaches manual localization annotations (bounding boxes, polygons, lesion mask).
        """
        if record_id not in self.records:
            raise KeyError(f"Record {record_id} not found.")

        rec = self.records[record_id]
        loc = rec["localization"]
        if bounding_boxes is not None:
            loc["bounding_boxes"] = bounding_boxes
        if polygons is not None:
            loc["polygons"] = polygons
        if mask_file is not None:
            loc["mask_file"] = mask_file

        has_annotations = bool(loc["bounding_boxes"] or loc["polygons"] or loc["mask_file"])
        loc["has_manual_annotations"] = has_annotations

        rec["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.save()
        return rec

    def get_summary(self) -> Dict[str, Any]:
        """
        Generates comprehensive dataset summary and readiness inventory.
        """
        total = len(self.records)
        by_crop = {}
        by_status = {"pending": 0, "reviewed": 0, "verified": 0, "disputed": 0}
        by_health = {"healthy": 0, "abnormal": 0, "unknown": 0}
        by_env = {}
        by_lighting = {}
        by_view = {}
        manual_annotated_count = 0

        for r in self.records.values():
            c_id = r["crop"]["crop_id"]
            by_crop[c_id] = by_crop.get(c_id, 0) + 1
            st = r.get("annotation_status", "pending")
            by_status[st] = by_status.get(st, 0) + 1
            hs = r.get("health_status", "unknown")
            by_health[hs] = by_health.get(hs, 0) + 1

            cond = r.get("capture_conditions", {})
            env = cond.get("environment", "unknown")
            by_env[env] = by_env.get(env, 0) + 1
            lt = cond.get("lighting", "unknown")
            by_lighting[lt] = by_lighting.get(lt, 0) + 1
            vw = cond.get("capture_view", "unknown")
            by_view[vw] = by_view.get(vw, 0) + 1

            if r.get("localization", {}).get("has_manual_annotations"):
                manual_annotated_count += 1

        # Check status for Vietnam 8 key crops
        crop_readiness = []
        for cid, meta in VIETNAM_KEY_CROPS.items():
            model_exists = self.check_model_exists(cid)
            img_count = by_crop.get(cid, 0)
            verified_count = sum(1 for r in self.records.values() if r["crop"]["crop_id"] == cid and r.get("annotation_status") == "verified")
            
            if not model_exists:
                status_desc = "CHƯA CÓ MÔ HÌNH (Cần dữ liệu huấn luyện & thẩm định)"
                category = "requires_model_and_data"
            elif img_count == 0:
                status_desc = "CÓ MÔ HÌNH - CHƯA CÓ ẢNH THỰC ĐỊA (Đang chờ thu thập mẫu)"
                category = "requires_field_data"
            elif verified_count == 0:
                status_desc = f"ĐANG THẨM ĐỊNH ({img_count} ảnh đã thu thập, chờ chuyên gia duyệt)"
                category = "collecting_and_validating"
            else:
                status_desc = f"ĐÃ THẨM ĐỊNH ({verified_count}/{img_count} ảnh đã xác thực)"
                category = "validated"

            crop_readiness.append({
                "crop_id": cid,
                "crop_name_vi": meta["name_vi"],
                "compatible_model_exists": model_exists,
                "field_images_count": img_count,
                "verified_images_count": verified_count,
                "readiness_status": status_desc,
                "category": category
            })

        return {
            "total_field_records": total,
            "crops_count": len(by_crop),
            "by_status": by_status,
            "by_health": by_health,
            "by_environment": by_env,
            "by_lighting": by_lighting,
            "by_capture_view": by_view,
            "manual_localization_annotations": manual_annotated_count,
            "vietnam_8_key_crops": crop_readiness
        }

    def export_csv(self) -> str:
        """
        Exports annotations to CSV string format.
        """
        headers = [
            "id", "filename", "crop_id", "crop_name_vi", "health_status",
            "disease_id", "disease_name_vi", "environment", "lighting", "capture_view",
            "province", "district", "annotation_status", "has_localization", "created_at"
        ]
        lines = [",".join(headers)]
        for r in self.records.values():
            loc = r.get("localization", {})
            has_loc = "true" if loc.get("has_manual_annotations") else "false"
            row = [
                r["id"],
                r["filename"],
                r["crop"]["crop_id"],
                f'"{r["crop"]["crop_name_vi"]}"',
                r["health_status"],
                r.get("diagnosis", {}).get("disease_id") or "",
                f'"{r.get("diagnosis", {}).get("disease_name_vi") or ""}"',
                r.get("capture_conditions", {}).get("environment", ""),
                r.get("capture_conditions", {}).get("lighting", ""),
                r.get("capture_conditions", {}).get("capture_view", ""),
                f'"{r.get("location", {}).get("province", "")}"',
                f'"{r.get("location", {}).get("district", "")}"',
                r.get("annotation_status", "pending"),
                has_loc,
                r.get("created_at", "")
            ]
            lines.append(",".join(row))
        return "\n".join(lines)
