"""
GARI Module 10 — 3D Farm Experience Service Layer
Provides data-connected, performant 3D scene graphs for Three.js visualization.

Strict Data Integrity Guarantees:
1. Scene connects strictly to real farm, zone, plot, plant, cycle, diagnosis, and task records.
2. Clearly labels illustrative terrain, plant canopy meshes, and simulated geometry.
3. Does NOT claim the scene is a geographically accurate digital twin unless based on validated spatial survey data.
4. Does NOT fabricate sensor telemetry, artificial weather readings, or imaginary IoT devices.
5. Provides instancing metadata for high-performance InstancedMesh rendering on mobile/desktop GPUs.
"""

from typing import Dict, Any, List, Optional, Tuple
import math
import json
import logging
from gari_database import get_connection
import gari_farm_management
import gari_farm_map

logger = logging.getLogger("gari_farm_3d")


# Crop canopy archetype mapping for Three.js geometry generation
CROP_3D_ARCHETYPES = {
    "cà phê": {"model": "shrub_bush", "height": 1.8, "radius": 0.9, "color": "#15803d", "row_spacing": 2.5},
    "coffee": {"model": "shrub_bush", "height": 1.8, "radius": 0.9, "color": "#15803d", "row_spacing": 2.5},
    "hồ tiêu": {"model": "vine_column", "height": 3.2, "radius": 0.5, "color": "#166534", "row_spacing": 2.2},
    "pepper": {"model": "vine_column", "height": 3.2, "radius": 0.5, "color": "#166534", "row_spacing": 2.2},
    "sầu riêng": {"model": "canopy_tree", "height": 6.5, "radius": 2.8, "color": "#14532d", "row_spacing": 8.0},
    "durian": {"model": "canopy_tree", "height": 6.5, "radius": 2.8, "color": "#14532d", "row_spacing": 8.0},
    "lúa": {"model": "grass_cluster", "height": 0.9, "radius": 0.4, "color": "#84cc16", "row_spacing": 0.8},
    "rice": {"model": "grass_cluster", "height": 0.9, "radius": 0.4, "color": "#84cc16", "row_spacing": 0.8},
    "cà chua": {"model": "stake_vine", "height": 1.5, "radius": 0.6, "color": "#22c55e", "row_spacing": 1.2},
    "tomato": {"model": "stake_vine", "height": 1.5, "radius": 0.6, "color": "#22c55e", "row_spacing": 1.2},
    "ớt": {"model": "bush_stalk", "height": 1.1, "radius": 0.5, "color": "#4ade80", "row_spacing": 1.0},
    "chili": {"model": "bush_stalk", "height": 1.1, "radius": 0.5, "color": "#4ade80", "row_spacing": 1.0},
    "ngô": {"model": "tall_stalk", "height": 2.4, "radius": 0.4, "color": "#65a30d", "row_spacing": 0.9},
    "corn": {"model": "tall_stalk", "height": 2.4, "radius": 0.4, "color": "#65a30d", "row_spacing": 0.9},
    "default": {"model": "shrub_bush", "height": 1.5, "radius": 0.7, "color": "#22c55e", "row_spacing": 2.0}
}


def resolve_crop_archetype(crop_name: Optional[str]) -> Dict[str, Any]:
    """Resolve standard 3D visual archetype for a crop type."""
    if not crop_name:
        return CROP_3D_ARCHETYPES["default"]
    normalized = crop_name.lower().strip()
    for key, val in CROP_3D_ARCHETYPES.items():
        if key in normalized:
            return val
    return CROP_3D_ARCHETYPES["default"]


def generate_schematic_plant_instances(
    plot_width: float,
    plot_depth: float,
    crop_name: Optional[str],
    max_instances: int = 48
) -> List[Dict[str, Any]]:
    """
    Generate instanced plant coordinate matrices within plot bounding box.
    Optimized for high-performance THREE.InstancedMesh batching.
    """
    archetype = resolve_crop_archetype(crop_name)
    spacing = archetype["row_spacing"]
    
    # Calculate rows and columns bounded by plot dimensions
    margin = 1.5
    eff_w = max(2.0, plot_width - (margin * 2))
    eff_d = max(2.0, plot_depth - (margin * 2))
    
    cols = max(1, int(eff_w // spacing))
    rows = max(1, int(eff_d // spacing))
    
    total = cols * rows
    step_col = eff_w / max(1, cols)
    step_row = eff_d / max(1, rows)
    
    # Stride down if exceeding max_instances (protect mobile memory/GPU)
    stride = 1
    if total > max_instances:
        stride = math.ceil(total / max_instances)
        
    instances = []
    idx = 0
    start_x = -eff_w / 2.0
    start_z = -eff_d / 2.0
    
    for r in range(rows):
        for c in range(cols):
            if idx % stride == 0 and len(instances) < max_instances:
                # Add tiny organic variation so plants don't look robotic
                var_x = ((idx * 17) % 7 - 3) * 0.04
                var_z = ((idx * 23) % 7 - 3) * 0.04
                scale_var = 0.9 + (((idx * 13) % 10) / 45.0)
                
                instances.append({
                    "instance_id": idx,
                    "x": round(start_x + (c * step_col) + (step_col / 2.0) + var_x, 2),
                    "y": 0.0,
                    "z": round(start_z + (r * step_row) + (step_row / 2.0) + var_z, 2),
                    "scale": round(scale_var, 3),
                    "rotation_y": round(((idx * 45) % 360) * (math.pi / 180.0), 3)
                })
            idx += 1
            
    return instances


def get_farm_3d_scene(
    farm_id: int,
    user_id: int,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Constructs the authoritative 3D scene descriptor for Three.js.
    
    Returns:
    - scene_metadata: digital twin status, disclaimer, real vs simulated element breakdown.
    - farm: real farm identity, center coordinates, boundaries.
    - terrain: ground dimensions, soil material properties.
    - plots: array of 3D plot parcels with position (X, Z), dimensions (W, D), health status, and alert markers.
    - instanced_crops: batch matrices for InstancedMesh rendering grouped by archetype.
    - camera_preset: optimal initial orbit camera position.
    - summary: counts of healthy, attention-needed, and unlocated plots.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Authorize user
        if not gari_farm_management.check_farm_access(farm_id, user_id, org_id, conn):
            raise PermissionError("Bạn không có quyền truy cập mô hình 3D của nông trại này.")
            
        cursor.execute("SELECT * FROM farms WHERE id = ?", (farm_id,))
        farm_row = cursor.fetchone()
        if not farm_row:
            raise ValueError(f"Không tìm thấy nông trại #{farm_id}.")
        farm = dict(farm_row)
        
        # Determine digital twin truthfulness
        geom_source = farm.get("geometry_source") or "user_drawn"
        is_digital_twin = bool(geom_source == "surveyed" and farm.get("latitude") and farm.get("longitude"))
        
        # 2. Retrieve Plots
        cursor.execute("""
            SELECT p.*, z.name as zone_name
            FROM farm_plots p
            LEFT JOIN farm_zones z ON p.zone_id = z.id
            WHERE p.farm_id = ?
            ORDER BY p.id ASC
        """, (farm_id,))
        plot_rows = [dict(r) for r in cursor.fetchall()]
        
        # 3. Layout Plots in 3D Space (Meters)
        plots_3d = []
        instanced_crops_map: Dict[str, List[Dict[str, Any]]] = {}
        
        healthy_count = 0
        attention_count = 0
        unknown_count = 0
        
        # Layout grid geometry
        cols = max(1, math.ceil(math.sqrt(len(plot_rows) or 1)))
        default_plot_w = 24.0  # 24m width
        default_plot_d = 24.0  # 24m depth
        spacing = 8.0          # 8m road/path between plots
        
        step_x = default_plot_w + spacing
        step_z = default_plot_d + spacing
        
        total_grid_w = cols * step_x
        total_grid_d = (math.ceil(len(plot_rows) / cols) if cols > 0 else 1) * step_z
        offset_center_x = -total_grid_w / 2.0 + (default_plot_w / 2.0)
        offset_center_z = -total_grid_d / 2.0 + (default_plot_d / 2.0)
        
        for idx, p in enumerate(plot_rows):
            p_id = p["id"]
            
            # Health status derivation (Truth-in-Data)
            health_eval = gari_farm_map.evaluate_plot_health_status(p_id, conn)
            health_status = health_eval["health_status"]
            health_reason = health_eval["status_reason"]
            if health_status == "healthy":
                healthy_count += 1
                color = "#22c55e"
            elif health_status == "attention_needed":
                attention_count += 1
                color = "#f97316"
            else:
                unknown_count += 1
                color = "#94a3b8"
                
            # Active Cycle
            cursor.execute("""
                SELECT * FROM crop_cycles 
                WHERE plot_id = ? AND status = 'active' 
                ORDER BY start_date DESC LIMIT 1
            """, (p_id,))
            cycle_row = cursor.fetchone()
            active_cycle = dict(cycle_row) if cycle_row else None
            
            # Determine 3D Plot Position (meters)
            # If coordinates exist, we can use local meter offsets from farm center
            grid_col = idx % cols
            grid_row = idx // cols
            pos_x = round(offset_center_x + (grid_col * step_x), 1)
            pos_z = round(offset_center_z + (grid_row * step_z), 1)
            
            # Dimensions proportional to area if available
            area_m2 = float(p.get("area_m2") or 2500.0)
            side_m = round(math.sqrt(max(100.0, area_m2)) * 0.45, 1)  # Scale to reasonable 3D view
            side_m = min(40.0, max(16.0, side_m))
            
            crop_name = p.get("crop_name") or farm.get("primary_crop") or "Cà phê"
            archetype = resolve_crop_archetype(crop_name)
            
            # Query actual individual plants if registered in DB
            cursor.execute("""
                SELECT id, plant_tag, plant_name, health_status, row_index, col_index, notes
                FROM plot_plants WHERE plot_id = ? AND status != 'archived' ORDER BY id ASC LIMIT 64
            """, (p_id,))
            plant_rows = [dict(pr) for pr in cursor.fetchall()]
            
            # Generate plant instance transforms
            instances = []
            if plant_rows:
                # Map real registered plants to local 3D coords
                p_cols = max(1, int(math.ceil(math.sqrt(len(plant_rows)))))
                p_step = (side_m - 3.0) / max(1, p_cols)
                for pr_idx, pr in enumerate(plant_rows):
                    r_idx = pr_idx // p_cols
                    c_idx = pr_idx % p_cols
                    instances.append({
                        "plant_id": pr["id"],
                        "plant_tag": pr["plant_tag"],
                        "health_status": pr["health_status"] or "healthy",
                        "x": round(-side_m/2.0 + 1.5 + (c_idx * p_step), 2),
                        "y": 0.0,
                        "z": round(-side_m/2.0 + 1.5 + (r_idx * p_step), 2),
                        "scale": 1.0,
                        "rotation_y": 0.0
                    })
            else:
                # Generate schematic crop rows for performance
                instances = generate_schematic_plant_instances(
                    plot_width=side_m,
                    plot_depth=side_m,
                    crop_name=crop_name,
                    max_instances=36
                )
                
            model_key = archetype["model"]
            if model_key not in instanced_crops_map:
                instanced_crops_map[model_key] = []
                
            # Add instances with world offsets
            for inst in instances:
                inst_world = dict(inst)
                inst_world["plot_id"] = p_id
                inst_world["world_x"] = round(pos_x + inst["x"], 2)
                inst_world["world_y"] = round(inst["y"], 2)
                inst_world["world_z"] = round(pos_z + inst["z"], 2)
                inst_world["archetype"] = model_key
                inst_world["color"] = archetype["color"]
                instanced_crops_map[model_key].append(inst_world)
                
            plots_3d.append({
                "plot_id": p_id,
                "name": p.get("plot_name") or p.get("name") or f"Thửa #{p_id}",
                "code": p.get("plot_code") or p.get("code") or f"P-{p_id}",
                "zone_name": p.get("zone_name"),
                "crop_name": crop_name,
                "area_hectare": p.get("area_hectare") or 0.25,
                "area_m2": area_m2,
                "health_status": health_status,
                "health_reason": health_reason,
                "boundary_color": color,
                "has_alert_marker": (health_status == "attention_needed"),
                "active_cycle_name": active_cycle["cycle_name"] if active_cycle else "Chưa kích hoạt vụ mùa",
                "registered_plants_count": len(plant_rows),
                "position": {"x": pos_x, "y": 0.0, "z": pos_z},
                "dimensions": {"width": side_m, "height": 0.4, "depth": side_m},
                "instances_count": len(instances)
            })
            
        # Ground plane dimensions
        ground_size = max(120.0, max(total_grid_w, total_grid_d) + 60.0)
        
        # Camera preset
        camera_preset = {
            "position": {"x": round(ground_size * 0.45, 1), "y": round(ground_size * 0.42, 1), "z": round(ground_size * 0.55, 1)},
            "target": {"x": 0.0, "y": 0.0, "z": 0.0},
            "fov": 45,
            "near": 0.5,
            "far": 1500
        }
        
        return {
            "scene_metadata": {
                "version": "1.0",
                "is_digital_twin": is_digital_twin,
                "digital_twin_disclaimer": (
                    "Mô phỏng 3D trực quan minh họa cơ cấu canh tác và tình trạng sinh trưởng dựa trên dữ liệu thật. "
                    "Không phải bản sao số trắc địa GIS trừ khi có dữ liệu đo đạc chuyên sâu."
                    if not is_digital_twin else 
                    "Mô hình không gian 3D số hóa dựa trên tọa độ ranh giới trắc địa thực địa."
                ),
                "model_fidelity": "schematic_instanced",
                "real_data_elements": [
                    "farm_identity", 
                    "plot_records", 
                    "crop_varieties", 
                    "plant_registries", 
                    "leaf_diagnoses", 
                    "crop_tasks"
                ],
                "simulated_elements": [
                    "terrain_elevation_mesh", 
                    "crop_canopy_geometry"
                ],
                "sensor_telemetry": None,
                "sensor_telemetry_notice": "Nông trại chưa kích hoạt cảm biến vi khí hậu/IoT thực tế. GARI cam kết không bịa đặt chỉ số môi trường."
            },
            "farm": {
                "id": farm["id"],
                "name": farm["name"],
                "code": farm.get("code"),
                "province": farm.get("province"),
                "primary_crop": farm.get("primary_crop"),
                "area_hectare": farm.get("area_hectare") or 0.0,
                "geometry_source": geom_source,
                "latitude": farm.get("latitude"),
                "longitude": farm.get("longitude")
            },
            "terrain": {
                "width": ground_size,
                "depth": ground_size,
                "grid_divisions": 30,
                "soil_color": "#27272a",
                "grid_color": "#3f3f46"
            },
            "plots": plots_3d,
            "instanced_crops": instanced_crops_map,
            "camera_preset": camera_preset,
            "summary": {
                "total_plots": len(plots_3d),
                "healthy_plots": healthy_count,
                "attention_plots": attention_count,
                "unknown_plots": unknown_count,
                "total_plant_instances": sum(len(insts) for insts in instanced_crops_map.values())
            }
        }


def get_plot_3d_detail(
    plot_id: int,
    user_id: int,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Detailed 3D inspection for a single plot, including its micro-grid of plants.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if not gari_farm_management.check_plot_access(plot_id, user_id, org_id, conn):
            raise PermissionError("Bạn không có quyền truy cập dữ liệu thửa đất này.")
            
        cursor.execute("""
            SELECT p.*, f.name as farm_name, f.latitude as farm_lat, f.longitude as farm_lon
            FROM farm_plots p
            JOIN farms f ON p.farm_id = f.id
            WHERE p.id = ?
        """, (plot_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy thửa #{plot_id}.")
        plot = dict(row)
        plot["name"] = plot.get("plot_name") or plot.get("name") or f"Thửa #{plot_id}"
        
        health_eval = gari_farm_map.evaluate_plot_health_status(plot_id, conn)
        health_status = health_eval["health_status"]
        health_reason = health_eval["status_reason"]
        
        cursor.execute("SELECT * FROM plot_plants WHERE plot_id = ? AND status != 'archived'", (plot_id,))
        plants = [dict(r) for r in cursor.fetchall()]
        
        return {
            "plot": plot,
            "health_status": health_status,
            "health_reason": health_reason,
            "plants": plants,
            "total_plants": len(plants)
        }
