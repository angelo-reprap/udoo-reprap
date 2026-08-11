def api_person_mails(request, crm_id):
    """Mailbox-Mails einer Person, ermittelt über ihre CRM-E-Mail-Adressen."""
    from elasticsearch import Elasticsearch
    from apps.abpe_crm.models import CrmEmailAddrBeanRel, CrmEmailAddress

    # 1) E-Mail-Adressen — Firma inkl. Ansprechpartner, Person nur eigene
    from apps.abpe_edms.owner_rollup import related_crm_ids_for_entity, email_addresses_for_crm_ids
    _mail_crm_ids = related_crm_ids_for_entity(crm_id)
    addresses = email_addresses_for_crm_ids(_mail_crm_ids)
    if not addresses:
        return JsonResponse({
            "ok": True, "total": 0, "addresses": [], "results": [],
            "hint": "Keine E-Mail-Adresse zu dieser Person im CRM hinterlegt.",
        })

    # 2) In abpe_emails suchen (match, weil from/to den vollen Header enthalten)
    try:
        size = int(request.GET.get("size") or 100)
    except ValueError:
        size = 100
    size = max(1, min(size, 500))

    should = []
    for a in addresses:
        should.append({"match_phrase": {"from_addr": a}})
        should.append({"match_phrase": {"to_addr": a}})

    must = []
    q = (request.GET.get("q") or "").strip()
    if q:
        must.append({"multi_match": {
            "query": q, "fields": ["subject^2", "body"], "operator": "and",
        }})

    body = {
        "size": size,
        "query": {"bool": {
            "should": should,
            "minimum_should_match": 1,
            "must": must,
        }},
        "sort": [{"date": {"order": "desc"}}],
        "_source": ["subject", "from_addr", "to_addr", "date", "folder",
                    "account", "message_id", "uid", "has_attachments", "size_bytes"],
    }

    try:
        es = Elasticsearch(["http://localhost:9200"])
        res = es.search(index="abpe_emails", body=body)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)[:200],
                             "addresses": addresses, "results": []}, status=200)

    results = []
    for h in res["hits"]["hits"]:
        s = h["_source"]
        # message_id im Index hat \r\n-Präfix + spitze Klammern -> säubern
        mid = (s.get("message_id") or "").strip()
        results.append({
            "id": h["_id"],
            "subject": s.get("subject") or "(kein Betreff)",
            "from_addr": s.get("from_addr") or "",
            "to_addr": s.get("to_addr") or "",
            "date": s.get("date") or "",
            "folder": s.get("folder") or "",
            "account": s.get("account") or "",
            "message_id": mid,
            "uid": s.get("uid") or "",
            "has_attachments": bool(s.get("has_attachments")),
            "size_bytes": s.get("size_bytes") or 0,
        })

    total = res["hits"]["total"]["value"]
    return JsonResponse({
        "ok": True,
        "total": total,
        "addresses": addresses,
        "results": results,
    })
