import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

import gari_assistant

def test_action_extraction():
    sample_llm_reply = """Chào bạn, vết bệnh này là đốm lá Alternaria solani.
1. Khảo sát ngay: Kiểm tra tầng lá thấp trong bán kính 2m.
2. Vệ sinh: Tỉa bỏ các lá vàng úa sát đất.
3. Theo dõi 48h: Quan sát quầng vàng quanh đốm bệnh.

```gari-action
{"title": "Kiểm tra tiến triển vết bệnh cà chua sau 48h", "due_days": 2, "priority": "high", "task_type": "scouting", "description": "Kiểm tra mặt dưới lá và đo lường kích thước vết bệnh sau đợt mưa."}
```
Chúc vườn cây của bạn sớm phục hồi!"""

    diagnosis_mock = {"id": 101, "crop_id": "Tomato", "farm_id": 1, "plot_id": 2}
    cleaned_text, actions = gari_assistant.extract_action_drafts(sample_llm_reply, diagnosis_mock)
    
    assert "```gari-action" not in cleaned_text, "Action block not stripped from visible text!"
    assert len(actions) == 1, f"Expected 1 action, got {len(actions)}"
    act = actions[0]
    assert act["title"] == "Kiểm tra tiến triển vết bệnh cà chua sau 48h"
    assert act["priority"] == "high"
    assert act["requires_confirmation"] is True
    assert act["diagnosis_id"] == 101
    print("PASS: Action extraction and draft parsing works perfectly!")

if __name__ == "__main__":
    test_action_extraction()
