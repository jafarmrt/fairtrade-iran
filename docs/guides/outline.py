import json, sys, pypdf
r = pypdf.PdfReader(sys.argv[1]); out = []
def walk(o):
    for x in o:
        if isinstance(x, list): walk(x)
        else: out.append([x.title.strip(), r.get_destination_page_number(x) + 1])
walk(r.outline); print(json.dumps(out, ensure_ascii=False))
