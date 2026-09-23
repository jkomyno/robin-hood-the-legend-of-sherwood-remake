"""Build a portable review gallery from existing, unmodified render sheets."""

import sys as _refinement_sys
from pathlib import Path as _RefinementPath
_refinement_legacy = str(_RefinementPath(__file__).resolve().parents[2] / 'blender')
if _refinement_legacy not in _refinement_sys.path:
    _refinement_sys.path.append(_refinement_legacy)

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
import shutil


FEEDBACK_SCRIPT = r"""
(() => {
  const cards = [...document.querySelectorAll('article[data-review-revision]')];
  const preview = document.querySelector('#review-export');
  const message = document.querySelector('#copy-status');
  const namespace = 'model-review-v1:' + document.title + ':';
  const key = card => namespace + card.id + ':' + card.dataset.reviewRevision;
  const clean = value => value.replace(/\s+/g, ' ').trim();
  function refresh() {
    const lines = cards.flatMap(card => {
      const decision = card.querySelector('.decision').value;
      const note = clean(card.querySelector('.review-note').value);
      if (!decision && !note) return [];
      return [`${card.id}: ${decision || 'feedback'}${note ? ' — ' + note : ''} [review ${card.dataset.reviewRevision}]`];
    });
    preview.value = lines.length ? document.title + '\n' + lines.join('\n') : '';
    document.querySelector('#review-count').textContent = `${lines.length} reviewed`;
    document.querySelector('#copy-reviews').disabled = !lines.length;
  }
  for (const card of cards) {
    const decision = card.querySelector('.decision');
    const note = card.querySelector('.review-note');
    const status = card.querySelector('.draft-status');
    try {
      const saved = JSON.parse(localStorage.getItem(key(card)) || 'null');
      if (saved) {
        if ([...decision.options].some(option => option.value === saved.decision && !option.disabled)) {
          decision.value = saved.decision;
        }
        note.value = typeof saved.note === 'string' ? saved.note : '';
        status.textContent = 'Restored saved review';
      }
    } catch {
      status.textContent = 'Browser storage unavailable; copy your results before closing.';
    }
    const save = () => {
      try {
        if (!decision.value && !note.value) localStorage.removeItem(key(card));
        else localStorage.setItem(key(card), JSON.stringify({decision: decision.value, note: note.value}));
        status.textContent = 'Saved in this browser';
      } catch {
        status.textContent = 'Could not save in this browser; copy your results before closing.';
      }
      message.textContent = '';
      refresh();
    };
    decision.addEventListener('change', save);
    note.addEventListener('input', save);
  }
  document.querySelector('#copy-reviews').addEventListener('click', async () => {
    refresh();
    try {
      await navigator.clipboard.writeText(preview.value);
      message.textContent = 'Copied. Paste into chat.';
    } catch {
      document.querySelector('#export-details').open = true;
      preview.focus();
      preview.select();
      let copied = false;
      try { copied = document.execCommand('copy'); } catch { /* Manual selection remains available. */ }
      message.textContent = copied ? 'Copied. Paste into chat.' : 'Press Ctrl+C / Cmd+C to copy the selected results.';
    }
  });
  refresh();
})();
"""

def build(index_path, output, *, pending_only=False, map_name=None):
    index_path = Path(index_path).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    data = json.loads(index_path.read_text())
    map_name = map_name if map_name is not None else data.get("map", "Derby")
    if not isinstance(map_name, str) or not map_name.strip():
        raise ValueError("Review gallery requires a nonempty map name")
    title = html.escape(map_name.strip() + " model review")
    items = data["items"]
    if pending_only:
        items = [item for item in items if not (str(item.get("user_approval", "")).lower().startswith("approved")
                 and item.get("technical_eligible", True))]
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate review identifiers")
    previous = output / "evidence.json"
    if previous.exists():
        digest = hashlib.sha256(previous.read_bytes()).hexdigest()[:16]
        archive = output / "history" / digest
        if not archive.exists():
            archive.mkdir(parents=True)
            for name in ("index.html", "evidence.json"):
                shutil.copyfile(output / name, archive / name)
            shutil.copytree(output / "images", archive / "images")
            if (output / "reports").exists():
                shutil.copytree(output / "reports", archive / "reports")
    records, cards = [], []
    status_counts = data.get('status_counts', {})
    status_summary = ('<p>' + html.escape(', '.join(
        f'{count} {status}' for status, count in sorted(status_counts.items()))) +
        '.</p>') if status_counts else ''
    missing = data.get('without_packets', [])
    missing_section = ''
    if missing:
        rows = ''.join('<tr><td>' + html.escape(item['name']) + '</td><td><code>' +
                       html.escape(item['id']) + '</code></td><td>' + html.escape(item['status']) +
                       '</td><td>' + html.escape(item.get('reason', '')) + '</td></tr>' for item in missing)
        missing_section = ('<section><h2>Assets awaiting complete review packets</h2>'
                           '<p>These assets are still in progress and are not ready for approval.</p>'
                           '<table><thead><tr><th>Asset</th><th>ID</th><th>Status</th><th>Details</th></tr></thead>'
                           '<tbody>' + rows + '</tbody></table></section>')
    for number, item in enumerate(items, 1):
        asset_id = item["id"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", asset_id):
            raise ValueError(f"Unsafe review identifier: {asset_id}")
        figures, evidence = [], {}
        sheets = [("solid", item.get("solid_label", "Solid geometry")),
                  ("textured", item.get("textured_label", "Original textures + shaded unknown surfaces"))]
        if item.get("context"):
            sheets.append(("context", "Original artwork with surrounding context"))
        for key, label in (("source_comparison", "Original artwork / before / corrected"),
                           ("source_comparison_secondary", "Additional source-camera comparison"),
                           ("source_trace", "Numbered source artwork corners"),
                           ("projection_errors", "Corrected mesh projected onto original artwork")):
            if item.get(key):
                sheets.append((key, item.get(key + "_label", label)))
        for key, label in (("revealed_solid", "Revealed interior geometry"),
                           ("revealed_textured", "Revealed interior original textures + shaded unknown surfaces"),
                           ("revealed_context", "Original revealed artwork with surrounding context")):
            if item.get(key):
                sheets.append((key, label))
        if item.get('stored_material_textured'):
            sheets.append(('stored_material_textured', 'Actual saved UVs and atlas materials'))
        for state in item.get('stored_material_states', []):
            if state.get('sheet'):
                key = 'stored_material_' + state['id'] + '_textured'
                item[key] = state['sheet']
                sheets.append((key, 'Actual saved materials: ' + html.escape(state['id'])))
        for key, label in sheets:
            source = Path(item[key])
            if not source.is_absolute():
                source = index_path.parent / source
            source = source.resolve(strict=True)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            relative = f"images/{asset_id}-{key}-{digest[:16]}.png"
            target = output / relative
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"Review image copy differs: {source}")
            evidence[key] = {"source": str(source), "file": relative, "sha256": digest}
            figures.append(f'<figure data-kind="{key}"><figcaption>{html.escape(label)}</figcaption>'
                           f'<a href="{relative}" target="_blank"><img src="{relative}" '
                           f'loading="lazy" alt="{html.escape(item["name"])} — {label}"></a></figure>')
        notes = item.get("notes", "")
        if isinstance(notes, list):
            notes = " ".join(notes)
        reports = {}
        report_links = []
        report_specs = [("validation", "Validation report"),
                           ("ownership", "Source ownership evidence"),
                           ("review", "Worker review and limitations"),
                           ("stored_material_audit", "Stored UV/material audit"),
                           ("stored_material_glb", "Actual exported GLB")]
        for state in item.get('stored_material_states', []):
            key = 'stored_material_' + state['id'] + '_audit'
            if Path(state['audit']).is_file():
                item[key] = state['audit']
                report_specs.append((key, 'Stored material audit: ' + html.escape(state['id'])))
        for key, label in report_specs:
            if not item.get(key):
                continue
            source = Path(item[key])
            if not source.is_absolute():
                source = index_path.parent / source
            source = source.resolve(strict=True)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            relative = f"reports/{asset_id}-{key}-{digest[:16]}{source.suffix}"
            target = output / relative
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"Review report copy differs: {source}")
            reports[key] = {"source": str(source), "file": relative, "sha256": digest}
            report_links.append(f'<a href="{relative}" target="_blank">{label}</a>')
        binding = {'images': {key: value['sha256'] for key, value in evidence.items()},
                   'reports': {key: value['sha256'] for key, value in reports.items()}}
        if item.get('model'):
            model = Path(item['model'])
            if not model.is_absolute():
                model = index_path.parent / model
            binding['model'] = hashlib.sha256(model.read_bytes()).hexdigest()
        revision = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
        approval_disabled = '' if item['status'] == 'ready-for-user' and item.get('technical_eligible', True) else ' disabled'
        controls = (f'<fieldset class="feedback"><legend>Your review</legend>'
                    f'<label>Decision <select class="decision" aria-label="Decision for {asset_id}">'
                    '<option value="">Not decided</option>'
                    f'<option value="approved"{approval_disabled}>Approve</option>'
                    '<option value="needs refinement">Needs refinement</option></select></label>'
                    f'<label>Feedback <textarea class="review-note" rows="2" '
                    f'aria-label="Feedback for {asset_id}" placeholder="What should change, or any notes?"></textarea></label>'
                    '<span class="draft-status" aria-live="polite"></span></fieldset>')
        cards.append(f'<article id="{asset_id}" data-review-revision="{revision[:16]}"><h2>{number}. {html.escape(item["name"])}</h2>'
                     f'<p><code>{html.escape(item["id"])}</code></p>'
                     f'<p class="status">{html.escape(item["status"])}</p>'
                     f'<p>{html.escape(notes)}</p><p>{" · ".join(report_links)}</p>'
                     f'{controls}<div class="sheets">{"".join(figures)}</div></article>')
        records.append({**item, "number": number, "images": evidence, "reports": reports,
                        "review_revision": revision})
    nav = "".join(f'<a href="#{item["id"]}">{n}. {html.escape(item["name"])}</a>' for n, item in enumerate(items, 1))
    document = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>'''+title+'''</title><style>
*{box-sizing:border-box}body{margin:0;background:#171a20;color:#eee;font:16px/1.5 system-ui,sans-serif}
header,main{max-width:1700px;margin:auto;padding:24px}h1{margin:0}h2{font-size:24px}
nav{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}a{color:#afd3ff}nav a{padding:5px 10px;background:#28313f;border-radius:5px}
article{padding:20px 0 40px;border-top:1px solid #455064;scroll-margin-top:15px}.status{color:#ffd898;font-weight:600}
.sheets{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}figcaption{padding:8px 0;color:#c2cddd}
img{display:block;width:100%;background:black}select{font:inherit;padding:6px;border-radius:5px}
.feedback{margin:16px 0;padding:12px;border:1px solid #455064;border-radius:6px;display:grid;gap:8px}
.feedback label{display:grid;gap:4px}.feedback select{width:fit-content}
textarea{font:inherit;width:100%;padding:8px;background:#202731;color:#eee;border:1px solid #65758c;border-radius:5px;resize:vertical}
button{font:inherit;padding:8px 14px;cursor:pointer;border-radius:5px}.draft-status,#copy-status{color:#b9d4b8;font-size:14px}
.review-export{position:sticky;bottom:0;background:#202731;border-top:1px solid #65758c;padding:12px 24px;z-index:2}
.review-export details{max-width:1000px}.review-export textarea{max-height:220px}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px;border-bottom:1px solid #455064;overflow-wrap:anywhere}
[hidden]{display:none!important}
figure[data-kind$=context] img{width:auto;max-width:100%;max-height:400px}figure[data-kind$=context]{grid-column:1/-1}
body[data-mode=solid] figure[data-kind$=textured],body[data-mode=textured] figure[data-kind$=solid]{display:none}
body:not([data-mode=both]) .sheets{grid-template-columns:1fr}
@media(max-width:1000px){.sheets{grid-template-columns:1fr}}
</style><body data-mode="both"><header><h1>'''+title+'''</h1>
<p>Geometry candidates, not generated textures. Gray means no accepted original texture.
Click any sheet for its full resolution. Review status does not imply user approval.</p>
'''+(f'<p><strong>{data.get("total_groups", len(items))} catalog assets'
      +(f' plus {data["supplemental_count"]} separate terrain packet' if data.get('supplemental_count') else '')+
      f'; {len(items)} pending review packets'
      f' and {len(missing)} assets awaiting packets.</strong></p>' if 'total_groups' in data else '')+'''
'''+status_summary+'''
'''+(f'<p><strong>Approved models are hidden. {len(items)} displayed packets; '
      f'{sum(item["status"] == "ready-for-user" for item in items)} ready for your decision.</strong> '
      'Items marked validation-pending or fix-needed are still being worked on.</p>' if pending_only else '')+'''
<label>Show <select id="mode"><option value="both">Both sheets</option><option value="solid">Solid geometry</option>
<option value="textured">Original textures + gray</option></select></label>
<label>Assets <select id="readiness"><option value="all">All pending assets</option>
<option value="ready">Ready for review</option></select></label><nav>'''+nav+'''</nav></header><main>'''+"".join(cards)+missing_section+'''</main>
<footer class="review-export"><button id="copy-reviews" type="button">Copy review results</button>
<span id="review-count"></span> <span id="copy-status" role="status"></span>
<details id="export-details"><summary>Preview / copy manually</summary>
<textarea id="review-export" readonly rows="5" aria-label="Review results to paste into chat"></textarea></details>
<small> Choices are saved in this browser for this revision. Paste the results into chat to submit them.</small></footer>
<script>
document.querySelector('#mode').addEventListener('change',e=>document.body.dataset.mode=e.target.value);
document.querySelector('#readiness').addEventListener('change',event=>{
  const onlyReady=event.target.value==='ready';
  for(const card of document.querySelectorAll('article')){
    const hidden=onlyReady&&card.querySelector('.status').textContent!=='ready-for-user';
    card.hidden=hidden;
    const link=document.querySelector('nav a[href="#'+card.id+'"]');
    if(link) link.hidden=hidden;
  }
});
</script><script>'''+FEEDBACK_SCRIPT+'''</script></body></html>'''
    (output / "index.html").write_text(document)
    (output / "evidence.json").write_text(json.dumps({"source_index": str(index_path), "items": records,
                                                    "without_packets": missing}, indent=2)+"\n")
    print(json.dumps({"gallery": str(output / "index.html"), "candidates": len(items), "images": sum(len(r["images"]) for r in records)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index")
    parser.add_argument("output")
    parser.add_argument("--pending-only", action="store_true", help="Hide explicitly approved candidates")
    parser.add_argument("--map-name", help="Map name; defaults to the manifest map or Derby for legacy manifests")
    args = parser.parse_args()
    build(args.index, args.output, pending_only=args.pending_only, map_name=args.map_name)
