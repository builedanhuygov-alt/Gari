with open('gari_database.py', 'r', encoding='utf-8') as f:
    db_text = f.read()

target_db = """        if status:
            cursor.execute("SELECT * FROM expert_applications WHERE status = ? ORDER BY id DESC", (status,))"""

replacement_db = """        if status:
            if status in ('pending', 'submitted'):
                cursor.execute("SELECT * FROM expert_applications WHERE status IN ('pending', 'submitted') ORDER BY id DESC")
            else:
                cursor.execute("SELECT * FROM expert_applications WHERE status = ? ORDER BY id DESC", (status,))"""

if target_db in db_text:
    db_text = db_text.replace(target_db, replacement_db, 1)
    with open('gari_database.py', 'w', encoding='utf-8') as f:
        f.write(db_text)
    print("Updated gari_database.py list_expert_applications status handling.")

with open('api_server.py', 'r', encoding='utf-8') as f:
    api_text = f.read()

# 1. Fix apply_expert_api
target_apply = """    app_data = payload.model_dump()
    result = gari_database.create_expert_application(current_user["id"], app_data)"""

replacement_apply = """    app_data = payload.model_dump()
    app_data.setdefault("email", current_user.get("email", ""))
    app_data.setdefault("institution", app_data.get("organization", ""))
    app_data.setdefault("degree", app_data.get("degree_details") or app_data.get("title", ""))
    app_data.setdefault("specialization", ", ".join(app_data.get("specialties", [])))
    app_data.setdefault("primary_crops", app_data.get("specialties", []))
    result = gari_database.create_expert_application(data=app_data, user_id=current_user["id"])"""

if target_apply in api_text:
    api_text = api_text.replace(target_apply, replacement_apply, 1)
    print("Updated apply_expert_api argument order and mappings in api_server.py.")

# 2. Fix host_review_expert_application_api
target_review = """    res = gari_database.review_expert_application(
        app_id=app_id,
        reviewer_id=current_host["id"],
        action=payload.action,
        admin_notes=payload.admin_notes or "",
        commission_rate=payload.commission_rate or 0.15
    )"""

replacement_review = """    res = gari_database.review_expert_application(
        app_id=app_id,
        action=payload.action,
        host_id=current_host["id"],
        reason=payload.admin_notes or ""
    )"""

if target_review in api_text:
    api_text = api_text.replace(target_review, replacement_review, 1)
    print("Updated review_expert_application arguments in api_server.py.")

# 3. Fix host_list_expert_applications_api call
target_list_apps = "apps = gari_database.list_expert_applications(status=status, limit=limit, offset=offset)"
replacement_list_apps = "apps = gari_database.list_expert_applications(status=status)"

if target_list_apps in api_text:
    api_text = api_text.replace(target_list_apps, replacement_list_apps, 1)
    print("Updated host_list_expert_applications_api call.")

with open('api_server.py', 'w', encoding='utf-8') as f:
    f.write(api_text)

print("Saved changes in api_server.py")
