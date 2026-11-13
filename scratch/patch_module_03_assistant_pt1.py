import re
from pathlib import Path

path = Path("gari_assistant.py")
content = path.read_text(encoding="utf-8")

# 1. Update PROVIDER definitions to include MOCK
old_prov = '''# Supported Providers
PROVIDER_DISABLED = "disabled"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai_compatible"
PROVIDER_ANTHROPIC = "anthropic"'''

new_prov = '''# Supported Providers
PROVIDER_DISABLED = "disabled"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai_compatible"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_MOCK = "mock"'''

content = content.replace(old_prov, new_prov)

# 2. Update is_configured in get_assistant_config()
old_is_conf = '''    is_configured = bool(provider != PROVIDER_DISABLED and api_key and len(api_key.strip()) > 5)'''

new_is_conf = '''    citations_enabled = bool(db_configs.get("assistant_citations_enabled", "1") in ("1", "true", "True"))
    deep_dive_enabled = bool(db_configs.get("assistant_deep_dive_enabled", "1") in ("1", "true", "True"))

    if provider == PROVIDER_MOCK:
        is_configured = True
    else:
        is_configured = bool(provider != PROVIDER_DISABLED and api_key and len(api_key.strip()) > 5)'''

content = content.replace(old_is_conf, new_is_conf)

# 3. Update return dict of get_assistant_config()
old_cfg_ret = '''        "temperature": temperature,
        "timeout_sec": timeout_sec,
        "is_configured": is_configured,
    }'''

new_cfg_ret = '''        "temperature": temperature,
        "timeout_sec": timeout_sec,
        "citations_enabled": citations_enabled,
        "deep_dive_enabled": deep_dive_enabled,
        "is_configured": is_configured,
    }'''

content = content.replace(old_cfg_ret, new_cfg_ret)

path.write_text(content, encoding="utf-8")
print("gari_assistant.py part 1 applied.")
