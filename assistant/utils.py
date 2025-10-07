import re
import base64


def get_query(query, word):
    pattern = rf"\b{re.escape(word)}\b(.*)"
    m = re.search(pattern, query, re.IGNORECASE)
    if m:
        query = m.group(1).strip()
        if len(query) < 3:
            return
        return query
    else:
        return None


def is_b64(data):
    try:
        return base64.b64encode(base64.b64decode(data)) == data
    except Exception:
        return False
